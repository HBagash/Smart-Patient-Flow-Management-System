# Smart-Patient-Flow-Management-System

If you're running into permission issues when attempting to operate this software enter this command in powershell: Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process

Set up a new python virtual environment:
python -m venv venv

Activate this new virtual environment:
venv\Scripts\Activate

python -m pip install --upgrade pip

You may need to manually install PyTorch if you require CUDA (For 5070 TI):
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

Now you can install all the other dependencies:
pip install -r requirements.txt

To run the software:
python manage.py runserver

To stop the run simply go to terminal and press "CTRL + C"

To populate database type this in the terminal: python manage.py simulate_data --sessions=1000 --days=56

(Creates 1000 sessions for the past 8 weeks)
