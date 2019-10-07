FROM bistromath/gnuradio:v3.8

ENV num_threads 10
MAINTAINER bistromath@gmail.com version: 0.1

WORKDIR /opt

RUN apt install -y python3-zmq python3-scipy

RUN mkdir gr-air-modes
COPY . gr-air-modes/
WORKDIR /opt/gr-air-modes
RUN mkdir build && cd build && cmake ../ && make -j${num_threads} && make install && ldconfig
