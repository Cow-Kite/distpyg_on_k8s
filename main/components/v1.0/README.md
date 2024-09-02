## 1. pod_config.yaml 자동 생성
### 1-1. configMap 생성
### 1-2. configMap의 value값으로 pod_config.yaml 생성 (pod-0, pod-1 ...)
### 장점: configMap을 한 번 구성해놓으면, pod를 생성할때마다 가져다 사용
### 단점 
### 1) pod의 개수가 증가할수록, configMap의 환경변수도 수동으로 수정
### 단점: 2) pod의 이름이 바뀌면, configMap의 환경변수도 수동으로 수정
