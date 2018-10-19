# hoomaluo-pi-pm
Repository for the Python code for the RPi of the Hoomaluo Power Monitor.

## Getting started
From the home directory of your RPi, clone this github directory:
```sh
cd
git clone https://github.com/hlmeS/hoomaluo-pi-pm.git
```

Looking at the files in our `src` directory, you will see the following.

```sh
cd hoomaluo-pi-pm/src/
ls
```
```pseudo
-rw-r--r-- 1 pi pi 11724 Oct  6 07:05 app.py
-rw-r--r-- 1 pi pi   148 Oct  6 07:05 checkpython.sh
-rw-r--r-- 1 pi pi   328 Oct  6 07:05 config-default.ini
-rw-r--r-- 1 pi pi    40 Oct  6 07:05 requirements.txt
```

Before being able to run the `app.py` file, make sure that all the requirements are installed, if you're not sure or if they're not, install them:
```sh
sudo pip3 install -r requirements.txt
```
Note, you may need to `sudo pip3 install --upgrade pyserial` if you get errors such as `AttributeError: 'Serial' object has no attribute 'is_open'`.

To run the python app, make sure to copy the `confit-default.ini` to `config.ini` and to update its content to match the installation and purpose of the device. To run the script and observe output in the console, set `debug` to `True` and run `python3 app.py`, otherwise set it to `False` and run `bash checkpython.sh`. To check if the script is running, run `pgrep -f app.py`.

## Crontab

To execute the python script on startup and check on it every so many minutes (e.g. 15), add these by first typing `crontab -e`. Then add these two lines to the end of the file:
```sh
@reboot cd ~/hoomaluo-pi-pm/src && python3 app.py > test.out &
*/15* * * * bash ~/hoomaluo-pi-pm/src/checkpython.sh
```
