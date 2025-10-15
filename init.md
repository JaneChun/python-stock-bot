# 설치 경로 확인

py -0p

# 버전, bit 확인

py --list

# 작업 폴더로 이동

cd C:\Users\jieun\Documents\python-stock-bot

# 가상환경 생성 (venv)

python -m venv python_32

# 경로 지정하여 실행

"C:\Program Files (x86)\Python311-32\python.exe" -m venv python_32

# 활성화

python_32\Scripts\activate
python_32\Scripts\activate.bat

# # 가상환경 생성 (Anaconda)

conda create -n kiwoom_32
conda activate kiwoom_32
conda config --env --set subdir win-32
conda install python=3.10

python -c "import platform; print(platform.architecture())"

# 패키지 설치

python -m pip install --upgrade pip
python -m pip install --upgrade setuptools

conda install pandas matplotlib
pip install pykrx matplotlib pykiwoom
