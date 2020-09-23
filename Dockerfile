FROM biocommons/dockerbase:1.1

COPY . /app/
WORKDIR /app
RUN python3 setup.py install

EXPOSE 5000

CMD ["python3", "-m", "anyvar.restapi"]
