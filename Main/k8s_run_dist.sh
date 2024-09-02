PYG_WORKSPACE=$PWD 
#USER="gnn" 
PY_EXEC="python3"
EXEC_SCRIPT="${PYG_WORKSPACE}/node_ogb_cpu.py" 
CMD="cd ${PYG_WORKSPACE}; ${PY_EXEC} ${EXEC_SCRIPT}" 

NUM_PODS=2 

DATASET=ogbn-products

DATASET_ROOT_DIR="./data/partitions/${DATASET}/${NUM_PODS}-parts"
# Number of epochs:
NUM_EPOCHS=10

# The batch size:
BATCH_SIZE=1024

# Fanout per layer:
NUM_NEIGHBORS="5,5,5"

# Number of workers for sampling:
NUM_WORKERS=2
CONCURRENCY=4

# DDP Port
DDP_PORT=11111

# POD configuration path:
POD_CONFIG=${PYG_WORKSPACE}/pod_config.yaml

# stdout stored in `/logdir/logname.out`.
python3 k8s_launch.py --workspace ${PYG_WORKSPACE} --pod_config ${POD_CONFIG} --num_nodes ${NUM_PODS} --num_neighbors ${NUM_NEIGHBORS} --dataset_root_dir ${DATASET_ROOT_DIR} --dataset ${DATASET}  --num_epochs ${NUM_EPOCHS} --batch_size ${BATCH_SIZE} --num_workers ${NUM_WORKERS} --concurrency ${CONCURRENCY} "${CMD}" & pid=$!

echo "started k8s_launch.py: ${pid}"
trap "kill -2 $pid" SIGINT
wait $pid 
set +x 
