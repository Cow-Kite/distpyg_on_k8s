## 쿠버네티스와 Ceph를 활용한 GraphSAGE 분산 학습 프레임워크
### - 참여과제
과제명: 초거대 그래프의 지능적 고속 처리를 위한 그래프 DBMS 기술 개발<br>
참여 기관: 포스텍, 큐브리드, 경희대학교, __강원대학교__, 한국공개SW협회<br>
역할: __그래프 신경망 학습/추론 고속 병렬 처리 기술 개발__
### - Paper
__강소연__, 이상훈, 문양세, "쿠버네티스와 Ceph 환경을 활용한 GraphSAGE 분산 학습 프레임워크", 데이타베이스연구, Vol. 40, No. 2, pp.108-125, 2024.
### - 기술스택
Kubernetes, Docker, PyTorch, PyTorch Geometric, Ceph, Grafana, Prometheus
### - 발표자료
[석사학위청구논문심사.pdf](https://github.com/user-attachments/files/19434631/default.pdf) <br>
[석사학위청구논문심사.pptx](https://github.com/user-attachments/files/19434633/default.pptx)


## 프레임워크 동작 과정
__(1) Pod Creating__<br>
- 분산 학습 수행할 파드 생성<br>
- pod 0은 마스터 파드, pod 1~N은 워커 파드 담당<br>
- 파드의 볼륨으로 Ceph 스토리지 마운트<br>

__(2) Graph Partitioning__<br>
- 마스터 파드는 METIS로 그래프 데이터 파티셔닝 수행<br>
- 분할된 파티션들은 Ceph 스토리지에 저장<br>

__(3) Sampling__<br>
- 각 워커 파드는 Ceph 스토리지에 저장된 파티션으로 서브그래프 생성<br>
- 만약 필요한 vertex 정보가 다른 파티션에 있다면 다른 파드에게 RPC 통신으로 요청<br>

__(4) Distributed Training__<br>
- 생성된 서브그래프로 GraphSAGE 학습 수행<br>
- 각 워커 파드는 모델을 독립적으로 학습<br>

__(5) Synchronization__<br>
- 각 워커 파드에서 파라미터 계산 후, All-Reduce 연산 수행<br>
- 모든 파드의 모델이 동일한 파라미터로 업데이트 -> 모델의 일관성 보장<br>

![image](https://github.com/user-attachments/assets/893e59a1-a2b0-4ef3-bc31-a49d8c124519)
