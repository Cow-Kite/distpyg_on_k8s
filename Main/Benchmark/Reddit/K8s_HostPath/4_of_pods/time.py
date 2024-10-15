import re

# 로그 파일 경로
log_file_path = 'pod0_sn05.txt'

# 정규 표현식 패턴 수정
train_it_pattern = re.compile(r"Train: epoch=\d+, it=\d+, loss=[\d.]+, time=([\d.]+), batch_time=[\d.]+, grad_time=[\d.]+, update_time=[\d.]+")
train_epoch_pattern = re.compile(r"Train epoch \d+ END: loss=[\d.]+, time=([\d.]+), sync_time=[\d.]+")
test_it_pattern = re.compile(r"Test: epoch=\d+, it=\d+, acc=[\d.]+, time=([\d.]+)")  # Test 로그 형식에 맞춘 패턴

# 시간 데이터를 저장할 리스트
train_it_times = []
train_epoch_times = []
test_it_times = []

# 로그 파일 읽기
with open(log_file_path, 'r') as file:
    for line in file:
        # Train iteration 시간 추출
        train_it_match = train_it_pattern.search(line)
        if train_it_match:
            train_it_times.append(float(train_it_match.group(1)))

        # Train epoch 시간 추출 (END 시점의 time 값 사용)
        train_epoch_match = train_epoch_pattern.search(line)
        if train_epoch_match:
            train_epoch_times.append(float(train_epoch_match.group(1)))

        # Test iteration 시간 추출
        test_it_match = test_it_pattern.search(line)
        if test_it_match:
            test_it_times.append(float(test_it_match.group(1)))

# 평균 계산
train_it_avg_time = sum(train_it_times) / len(train_it_times) if train_it_times else 0.0
train_epoch_avg_time = sum(train_epoch_times) / len(train_epoch_times) if train_epoch_times else 0.0
test_it_avg_time = sum(test_it_times) / len(test_it_times) if test_it_times else 0.0

# 결과 출력
print(f"Train it 평균 시간: {train_it_avg_time:.5f} 초")
print(f"Train epoch 평균 시간: {train_epoch_avg_time:.5f} 초")
print(f"Test it 평균 시간: {test_it_avg_time:.5f} 초")
