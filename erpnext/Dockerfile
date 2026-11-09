FROM frappe/erpnext:v16.53.0
ARG BUILD_VERSION=0.1.15
ARG BUILD_ARCH=aarch64
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="addon" io.hass.arch="${BUILD_ARCH}"
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends mariadb-server redis-server redis-tools supervisor git && rm -rf /var/lib/apt/lists/* && mkdir -p /opt/ha-erpnext /run/mysqld && chown mysql:mysql /run/mysqld
USER frappe
WORKDIR /home/frappe/frappe-bench
RUN node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (!((a===20&&b>=19)||(a===22&&b>=12)||a>22)) process.exit(1)'
RUN python3 -c 'import json,pathlib;p=pathlib.Path("sites/common_site_config.json");d=json.loads(p.read_text()) if p.exists() else {};d["socketio_port"]=9000;p.write_text(json.dumps(d,indent=2))'
RUN bench get-app --branch develop https://github.com/frappe/builder.git && bench get-app --branch develop https://github.com/frappe/studio.git
USER root
COPY kanban/Kanban.vue /home/frappe/frappe-bench/apps/studio/frontend/src/components/AppLayout/Kanban.vue
COPY kanban/Kanban.json /home/frappe/frappe-bench/apps/studio/frontend/src/json_types/studio/Kanban.json
COPY kanban/patch.py /opt/ha-erpnext/patch_kanban.py
RUN python3 /opt/ha-erpnext/patch_kanban.py && chown frappe:root /home/frappe/frappe-bench/apps/studio/frontend/src/components/AppLayout/Kanban.vue /home/frappe/frappe-bench/apps/studio/frontend/src/json_types/studio/Kanban.json /home/frappe/frappe-bench/apps/studio/frontend/src/json_types/index.ts /home/frappe/frappe-bench/apps/studio/frontend/src/utils/constants.js /home/frappe/frappe-bench/apps/studio/frontend/src/globals.ts /home/frappe/frappe-bench/apps/studio/frontend/src/data/components.ts
USER frappe
RUN cd apps/studio && yarn build
USER root
COPY startup.py /opt/ha-erpnext/startup.py
COPY supervisord.conf /opt/ha-erpnext/supervisord.conf
RUN chmod 755 /opt/ha-erpnext/startup.py
WORKDIR /home/frappe/frappe-bench
ENTRYPOINT ["python3","-u","/opt/ha-erpnext/startup.py"]
