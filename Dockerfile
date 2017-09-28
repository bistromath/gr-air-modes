FROM bistromath/gnuradio:3.7.11

ENV num_threads 10
MAINTAINER bistromath@gmail.com version: 0.1

WORKDIR /opt
RUN mkdir gr-air-modes
COPY . gr-air-modes/
WORKDIR /opt/gr-air-modes
RUN mkdir build && cd build && cmake ../ && make -j${num_threads} && make install && ldconfig
