#!/bin/bash
#

set -x

exec > >(sudo tee install.log)
exec 2>&1

echo "start installing....."
DIR=$(cd $(dirname "${BASH_SOURCE[0]}") && pwd)
source $DIR/install.conf

sudo curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
source /etc/lsb-release
echo "deb https://repos.influxdata.com/${DISTRIB_ID,,} ${DISTRIB_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/influxdb.list

sudo apt-get update -y || exit 1
sudo apt-get install -y libmysqlclient-dev mysql-client mysql-server ntp ntpdate graphviz || exit 1
sudo apt-get install -y git python-pip python-setuptools python-tox python-dev gcc rabbitmq-server celeryd librabbitmq-dev openssl || exit 1
sudo apt-get install -y apache2 libapache2-mod-wsgi || exit 1
sudo apt-get install -y influxdb || exit 1

cd ${ENERGY_SAVING_DIR}

sudo pip install jupyter || exit 1
sudo pip install -r requirements.txt -r test-requirements.txt || exit 1
sudo python setup.py install || exit 1

for NTP_SERVER in $NTP_SERVERS; do
    sed -i "/prepend customized ntp servers above/i \
server $NTP_SERVER iburst" /etc/ntp.conf
    sed -i "/prepend customized ntp servers above/i \
$NTP_SERVER" /etc/ntp/step-tickers
done
sudo systemctl enable ntp.service
sudo systemctl stop ntp.service
sudo ntpdate $NTP_SERVERS || exit 1
sudo systemctl restart ntp.service
sudo systemctl status ntp.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart ntpd"
    exit 1
else
    echo "ntpd is restarted"
fi

export MYSQL_SERVER=${MYSQL_SERVER:-"${MYSQL_SERVER_IP}:${MYSQL_SERVER_PORT}"}
if [-f /etc/energy_saving/settings]; then
    sudo sed -i "s/DATABASE_TYPE\\s*=.*/DATABASE_TYPE = 'mysql'/g" /etc/energy_saving/settings
    sudo sed -i "s/DATABASE_USER\\s*=.*/DATABASE_USER = '$MYSQL_USER'/g" /etc/energy_saving/settings
    sudo sed -i "s/DATABASE_PASSWORD\\s*=.*/DATABASE_PASSWORD = '$MYSQL_PASSWORD'/g" /etc/energy_saving/settings
    sudo sed -i "s/DATABASE_SERVER\\s*=.*/DATABASE_SERVER = '$MYSQL_SERVER'/g" /etc/energy_saving/settings
    sudo sed -i "s/DATABASE_PORT\\s*=.*/DATABASE_PORT = $MYSQL_SERVER_PORT/g" /etc/energy_saving/settings
    sudo sed -i "s/DATABASE_NAME\\s*=.*/DATABASE_NAME = '$MYSQL_NAME'/g" /etc/energy_saving/settings
fi

sudo systemctl restart mysql.service
sudo systemctl status mysql.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart mysql server"
    exit 1
else
    echo "mysql server is restarted"
fi
sudo mysqladmin -u${MYSQL_USER} -p"${MYSQL_OLD_PASSWORD}" password ${MYSQL_PASSWORD}
if [[ "$?" != "0" ]]; then
    echo "setting up mysql server initial password"
    sudo mysqladmin -u ${MYSQL_USER} password ${MYSQL_PASSWORD} || exit 1
    echo "mysql server password is initialized"
else
    echo "mysql serverpassword is updated"
fi
sudo mysql -u${MYSQL_USER} -p${MYSQL_PASSWORD} -e "show databases;" || exit 1
echo "mysql server password set succeeded"

sudo mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "GRANT ALL ON *.* to '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}'; flush privileges;" || exit 1
echo "mysql server privileges are updated"

sudo mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "GRANT ALL ON *.* to '${MYSQL_USER}'@'${MYSQL_SERVER_IP}' IDENTIFIED BY '${MYSQL_PASSWORD}'; flush privileges;" || exit 1
echo "mysql server privileges are updated"

sudo sudo mysql -h${MYSQL_SERVER_IP} --port=${MYSQL_SERVER_PORT} -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "drop database ${MYSQL_DATABASE};" || exit 1
sudo sudo mysql -h${MYSQL_SERVER_IP} --port=${MYSQL_SERVER_PORT} -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "create database ${MYSQL_DATABASE};" || exit 1
echo "mysql database is created"
sudo mkdir -p /var/log/energy_saving || exit 1
sudo chmod 777 /var/log/energy_saving || exit 1
sudo mkdir -p /var/www/energy_saving_web || exit 1
sudo chmod 777 /var/www/energy_saving_web || exit 1
sudo mkdir -p /opt/energy_savivng || exit 1
sudo chmod 777 /opt/energy_saving || exit 1

sudo -i jupyter notebook --generate-config --allow-root || exit 1
sudo cp -f conf/jupyter.service /etc/systemd/system || exit 1
sudo cp -n conf/energy-saving.conf /etc/apache2/sites-available/ || exit 1
sudo sed -i "s/\$ENERGY_SAVING_PORT/$ENERGY_SAVING_PORT/g" /etc/apache2/sites-available/energy-saving.conf || exit 1

sudo apt-get install python-software-properties || exit 1
sudo curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash - || exit 1
sudo apt-get install nodejs || exit 1

cd web
sudo npm install || exit 1
sudo npm run build || exit 1
sudo cp -rf build/* /var/www/energy_saving_web/ || exit 1
cd ..
sudo chmod -R 777 /var/www/energy_saving_web || exit 1

sudo a2ensite energy-saving.conf || exit 1

sudo energy-saving-db-manage upgrade heads || exit 1
echo "db schema is created"

sudo systemctl daemon-reload
sudo systemctl enable jupyter.service
sudo restart jupyter.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart jupyter"
    exit 1
else
    echo "jupyter is restarted"
fi

sudo systemctl enable apache2.service
sudo systemctl restart apache2.service
sudo systemctl status apache2.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart apache2"
    exit 1
else
    echo "apache2 is restarted"
fi

sudo systemcl enable influxdb.service
sudo systemctl restart influxdb.service
sudo systemctl status influxdb.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart influxdb"
    exit 1
else
    echo "influxdb is restarted"
fi
sleep 10
sudo influx -execute "CREATE DATABASE energy_saving" || exit 1
sudo influx -execute "CREATE RETENTION POLICY forever ON energy_saving DURATION INF REPLICATION 1 DEFAULT" || exit 1

sudo rabbitmq-plugins enable rabbitmq_management || exit 1
sudo rabbitmqctl change_password guest guest || exit 1
sudo rabbitmqctl set_user_tags guest administrator || exit 1
sudo rabbitmqctl set_permissions -p / guest ".*" ".*" ".*" || exit 1

sudo systemctl enable energy-saving-celereyd.service
sudo systemctl restart energy-saving-celeryd.service
sudo systemctl status energy-saving-celeryd.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart energy-saving-celeryd"
    exit 1
else
    echo "energy-saving-celeryd is restarted"
fi

echo "install is done"
