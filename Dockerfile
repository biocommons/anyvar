FROM python:3.10

COPY . /app/
WORKDIR /app
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install .

EXPOSE 5000

CMD ["python3", "-m", "anyvar.restapi"]
