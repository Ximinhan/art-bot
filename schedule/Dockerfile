From registry.redhat.io/ubi9/ubi
RUN dnf install -y python3-devel python3-pip python3 && dnf clean all && pip3 install --upgrade pip && pip3 install redis pygithub slack_sdk
COPY check_schedule.py /check_schedule.py
