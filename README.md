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
-rw-r--r-- 1 pi pi   328 Oct  6 07:05 config.ini
-rw-r--r-- 1 pi pi    40 Oct  6 07:05 requirements.txt
```

Before being able to run the `app.py` file, make sure that all the requirements are installed, if you're not sure or if they're not, install them:
```sh
pip3 install requirements.txt
```
