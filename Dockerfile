FROM python:2.7
ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt
CMD python main.py
EXPOSE 8002
