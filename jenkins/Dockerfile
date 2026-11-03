# mall 测试 CI 镜像：Jenkins + Python(pytest) + JMeter + Allure CLI
# 说明：测试用例直接在 Jenkins 容器内执行（无需 docker-in-docker），
#      UI 用例通过 SELENIUM_REMOTE_URL 连接 selenium/standalone-chrome 容器。
FROM jenkins/jenkins:lts-jdk17

USER root
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv curl unzip ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai \
    LANG=C.UTF-8

# JMeter（性能阶段）
ARG JMETER_VERSION=5.6.3
RUN curl -fsSL -o /tmp/jmeter.zip \
        "https://mirrors.aliyun.com/apache/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.zip" \
    && unzip -q /tmp/jmeter.zip -d /opt \
    && rm -f /tmp/jmeter.zip \
    && ln -sfn /opt/apache-jmeter-${JMETER_VERSION} /opt/jmeter \
    && /opt/jmeter/bin/jmeter --version >/dev/null 2>&1 || echo "JMeter 安装校验跳过"

# Allure CLI（生成 HTML 报告）
ARG ALLURE_VERSION=2.30.0
RUN curl -fsSL -o /tmp/allure.zip \
        "https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/${ALLURE_VERSION}/allure-commandline-${ALLURE_VERSION}.zip" \
    && unzip -q /tmp/allure.zip -d /opt \
    && rm -f /tmp/allure.zip \
    && ln -sfn /opt/allure-${ALLURE_VERSION} /opt/allure || echo "Allure 安装跳过"

# 测试依赖（预装，流水线里无需联网装包）
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        -r /tmp/requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# Jenkins 插件：构建期安装到 ref/plugins，容器首次启动时自动复制到 JENKINS_HOME
COPY jenkins/plugins.txt /usr/share/jenkins/ref/plugins.txt
# 防御：去掉可能的 UTF-8 BOM，否则插件名首字符带 BOM 会 404
RUN sed -i '1s/^\xEF\xBB\xBF//' /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt \
        --plugin-download-directory /usr/share/jenkins/ref/plugins \
    && ls /usr/share/jenkins/ref/plugins | wc -l

ENV PATH=/opt/jmeter/bin:/opt/allure/bin:/usr/local/bin:$PATH

USER jenkins
