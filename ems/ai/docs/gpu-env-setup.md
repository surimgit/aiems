# GPU Environment Setup

이 문서는 Jupyter 서버에서 학습용 GPU 환경을 만드는 절차를 정리한 문서다.

## 목표

- Python `3.10` 학습 환경 생성
- Jupyter 커널 분리
- `GPU 0` 고정
- `torch` CUDA 인식 확인

## 전제

- Jupyter 기본 Python은 프로젝트 버전과 다를 수 있다.
- 기본 커널을 그대로 쓰지 않고 별도 conda env를 만든다.
- `CUDA_VISIBLE_DEVICES=0`은 설치 단계가 아니라 `torch import 전`에 적용한다.

## 설치 순서

1. `conda` 존재 확인
2. `ems-ai-py310` 환경 생성
3. `ipykernel` 설치
4. `Python (ems-ai-py310)` 커널 등록
5. PyTorch와 학습용 패키지 설치
6. 새 커널로 전환
7. 첫 셀에서 GPU 0 고정
8. `torch.cuda.device_count() == 1` 확인

## 설치 명령

```bash
conda create -n ems-ai-py310 python=3.10 -y
conda run -n ems-ai-py310 pip install ipykernel
conda run -n ems-ai-py310 python -m ipykernel install --user --name ems-ai-py310 --display-name "Python (ems-ai-py310)"
conda run -n ems-ai-py310 pip install -r requirements-train.txt
conda run -n ems-ai-py310 pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## 새 커널 첫 셀

```python
import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
```

## 확인 셀

```python
import torch

print("torch =", torch.__version__)
print("cuda available =", torch.cuda.is_available())
print("device count =", torch.cuda.device_count())
print("current device =", torch.cuda.current_device())
print("device name =", torch.cuda.get_device_name(0))
```

정상 기준:

- `cuda available = True`
- `device count = 1`
- `device name = NVIDIA H200 NVL`

## 주의

- `!nvidia-smi`는 서버 전체 GPU를 보여준다.
- 다른 사용자의 GPU 1 작업이 보이는 것은 정상이다.
- 판단 기준은 `torch.cuda.device_count()`와 현재 PID가 어느 GPU에 올라가는지다.
- 같은 커널에서 이미 `torch`를 import했으면 커널 재시작 후 다시 해야 한다.

## 실행 파일

- Jupyter 실행용 노트북: [../notebooks/01_gpu_env_setup.ipynb](../notebooks/01_gpu_env_setup.ipynb)
- 패키지 목록: [../requirements-train.txt](../requirements-train.txt)
