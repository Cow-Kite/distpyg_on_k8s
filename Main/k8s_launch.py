import argparse
import logging
import multiprocessing
import os
import queue
import re
import signal
import subprocess
import sys
import time
from functools import partial
from threading import Thread
from typing import Optional

def clean_runs(get_all_remote_pids, conn):
    """This process cleans up the remaining remote training tasks."""
    print("Cleanup runs")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    data = conn.recv()

    # If the launch process exits normally, don't do anything:
    if data == "exit":
        sys.exit(0)
    else:
        remote_pids = get_all_remote_pids()
        for pod_name, pids in remote_pids.items():
            kill_proc(pod_name, pids)
    print("Cleanup exits")

def kill_proc(pod_name, pids):
    """Execute kubectl command to kill the specified processes in the Pod."""
    curr_pid = os.getpid()
    killed_pids = []
    pids.sort()
    for pid in pids:
        assert curr_pid != pid
        print(f"Kill process {pid} in Pod {pod_name}", flush=True)
        kill_cmd = f"kubectl exec {pod_name} -- kill {pid}"
        subprocess.run(kill_cmd, shell=True)
        killed_pids.append(pid)
    for i in range(3):
        killed_pids = get_pids_to_kill(pod_name, killed_pids)
        if len(killed_pids) == 0:
            break
        else:
            killed_pids.sort()
            for pid in killed_pids:
                print(f"Kill process {pid} in Pod {pod_name}", flush=True)
                kill_cmd = f"kubectl exec {pod_name} -- kill -9 {pid}"
                subprocess.run(kill_cmd, shell=True)

def get_pids_to_kill(pod_name, killed_pids):
    """Get the process IDs that we want to kill but are still alive in the Pod."""
    killed_pids = [str(pid) for pid in killed_pids]
    killed_pids = ",".join(killed_pids)
    ps_cmd = f"kubectl exec {pod_name} -- ps -p {killed_pids} -h"
    res = subprocess.run(ps_cmd, shell=True, stdout=subprocess.PIPE)
    pids = []
    for p in res.stdout.decode("utf-8").split("\n"):
        ps = p.split()
        if len(ps) > 0:
            pids.append(int(ps[0]))
    return pids

def remote_execute(
    cmd: str,
    state_q: queue.Queue,
    pod_name: str,
) -> Thread:
    """Execute command line in the Pod via kubectl exec.

    Args:
        cmd: User-defined command (udf) to execute in the Pod.
        state_q: A queue collecting Thread exit states.
        pod_name: The name of the Pod to run the command in.

    Returns:
        thread: The thread who runs the command in the Pod.
            Returns when the command completes in the Pod.
    """
    kubectl_cmd = f'kubectl exec {pod_name} -- sh -c "{cmd}"'

    print(f"----- kubectl_cmd={kubectl_cmd} ")

    def run(kubectl_cmd, state_q):
        try:
            subprocess.check_call(kubectl_cmd, shell=True)
            state_q.put(0)
        except subprocess.CalledProcessError as err:
            print(f"Called process error {err}")
            state_q.put(err.returncode)
        except Exception:
            state_q.put(-1)

    thread = Thread(
        target=run,
        args=(
            kubectl_cmd,
            state_q,
        ),
    )
    thread.setDaemon(True)
    thread.start()
    time.sleep(0.2)
    return thread

def get_remote_pids(pod_name, cmd_regex):
    """Get the process IDs that run the command in the Pod."""
    pids = []
    curr_pid = os.getpid()
    ps_cmd = f"kubectl exec {pod_name} -- ps -aux | grep python | grep -v grep"
    res = subprocess.run(ps_cmd, shell=True, stdout=subprocess.PIPE)
    for p in res.stdout.decode("utf-8").split("\n"):
        ps = p.split()
        if len(ps) < 2:
            continue
        res = re.search(cmd_regex, p)
        if res is not None and int(ps[1]) != curr_pid:
            pids.append(ps[1])

    pid_str = ",".join([str(pid) for pid in pids])
    ps_cmd = f"kubectl exec {pod_name} -- pgrep -P {pid_str}"
    res = subprocess.run(ps_cmd, shell=True, stdout=subprocess.PIPE)
    pids1 = res.stdout.decode("utf-8").split("\n")
    all_pids = []
    for pid in set(pids + pids1):
        if pid == "" or int(pid) == curr_pid:
            continue
        all_pids.append(int(pid))
    all_pids.sort()
    return all_pids

def get_all_remote_pids(pod_names, udf_command):
    """Get all processes in the Pods."""
    remote_pids = {}
    for pod_name in pod_names:
        # When creating training processes in remote Pods, we may insert
        # some arguments in the commands. We need to use regular expressions to
        # match the modified command.
        cmds = udf_command.split()
        new_udf_command = " .*".join(cmds)
        pids = get_remote_pids(pod_name, new_udf_command)
        remote_pids[pod_name] = pids
    return remote_pids

def wrap_cmd_w_envvars(cmd: str, env_vars: str) -> str:
    """Wraps a CLI command with desired environment variables.

    Example:
        >>> cmd = "ls && pwd"
        >>> env_vars = "VAR1=value1 VAR2=value2"
        >>> wrap_cmd_w_envvars(cmd, env_vars)
        "(export VAR1=value1 VAR2=value2; ls && pwd)"
    """
    if env_vars == "":
        return f"{cmd}"
    else:
        return f"export {env_vars}; {cmd}"


def wrap_cmd_w_extra_envvars(cmd: str, env_vars: list) -> str:
    """Wraps a CLI command with extra environment variables.

    Example:
        >>> cmd = "ls && pwd"
        >>> env_vars = ["VAR1=value1", "VAR2=value2"]
        >>> wrap_cmd_w_extra_envvars(cmd, env_vars)
        "(export VAR1=value1 VAR2=value2; ls && pwd)"
    """
    env_vars = " ".join(env_vars)
    return wrap_cmd_w_envvars(cmd, env_vars)

def submit_all_jobs(args, udf_command, dry_run=False):
    if dry_run:
        print("Dry run mode, no jobs will be launched")

    servers_cmd = []
    pod_names = []
    thread_list = []

    # Get the Pod names of the cluster:
    with open(args.pod_config) as f:
        for line in f:
            pod_name = line.strip()
            pod_names.append(pod_name)

    state_q = queue.Queue()

    master_pod_name = pod_names[0]
    for i, pod_name in enumerate(pod_names):
        server_env_vars_cur = ""
        cmd = wrap_cmd_w_envvars(udf_command, server_env_vars_cur)
        cmd = (wrap_cmd_w_extra_envvars(cmd, args.extra_envs)
               if len(args.extra_envs) > 0 else cmd)

        #cmd = cmd[:-1]
        cmd += " --logging"
        cmd += f" --dataset_root_dir={args.dataset_root_dir}"
        cmd += f" --dataset={args.dataset}"
        cmd += f" --num_nodes={args.num_nodes}"
        cmd += f" --num_neighbors={args.num_neighbors}"
        cmd += f" --node_rank={i}"
        cmd += f" --master_addr={master_pod_name}"
        cmd += f" --num_epochs={args.num_epochs}"
        cmd += f" --batch_size={args.batch_size}"
        cmd += f" --num_workers={args.num_workers}"
        cmd += f" --concurrency={args.concurrency}"
        cmd += f" --ddp_port={args.ddp_port}"
        servers_cmd.append(cmd)

        if not dry_run:
            thread_list.append(
                remote_execute(cmd, state_q, pod_name))

    # Start a cleanup process dedicated for cleaning up remote training jobs:
    conn1, conn2 = multiprocessing.Pipe()
    func = partial(get_all_remote_pids, pod_names, udf_command)
    process = multiprocessing.Process(target=clean_runs, args=(func, conn1))
    process.start()

    def signal_handler(signal, frame):
        logging.info("Stop launcher")
        conn2.send("cleanup")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    err = 0
    for thread in thread_list:
        thread.join()
        err_code = state_q.get()
        if err_code != 0:
            err = err_code  # Record error code:

    conn2.send("exit")
    process.join()
    if err != 0:
        print("Task failed")
        sys.exit(-1)
    print("=== fully done ! === ")

def main():
    parser = argparse.ArgumentParser(description="Launch a distributed job")
    parser.add_argument(
        "--pod_config",
        required=True,
        type=str,
        help="File of Pod configuration for server processes",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        required=True,
        help="Path of user directory of distributed tasks",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="ogbn-products",
        help="The name of the dataset",
    )
    parser.add_argument(
        "--dataset_root_dir",
        type=str,
        default='../../data/products',
        help="The root directory (relative path) of partitioned dataset",
    )
    parser.add_argument(
        "--num_nodes",
        type=int,
        default=2,
        help="Number of distributed pods",
    )
    parser.add_argument(
        "--num_neighbors",
        type=str,
        default="15,10,5",
        help="Number of node neighbors sampled at each layer",
    )
    parser.add_argument(
        "--node_rank",
        type=int,
        default=0,
        help="The current node rank",
    )
    parser.add_argument(
        "--num_training_procs",
        type=int,
        default=2,
        help="The number of training processes per node",
    )
    parser.add_argument(
        "--master_addr",
        type=str,
        default='worker-0',
        help="The master address for RPC initialization",
    )
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=100,
        help="The number of training epochs",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1024,
        help="Batch size for training and testing",
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=2,
        help="Number of sampler sub-processes",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Number of maximum concurrent RPC for each sampler",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=0.0004,
        help="Learning rate",
    )
    parser.add_argument(
        '--ddp_port',
        type=int,
        default=11111,
        help="Port used for PyTorch's DDP communication",
    )
    parser.add_argument(
        "--extra_envs",
        nargs="+",
        type=str,
        default=[],
        help=("Extra environment parameters be set. For example, you can set "
              "the 'LD_LIBRARY_PATH' by adding: --extra_envs "
              "LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH"),
    )
    args, udf_command = parser.parse_known_args()

    udf_command = str(udf_command[0])
    if "python" not in udf_command:
        raise RuntimeError("Launching script does only support a Python "
                           "executable file")
    submit_all_jobs(args, udf_command)


if __name__ == "__main__":
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(format=fmt, level=logging.INFO)
    main()
