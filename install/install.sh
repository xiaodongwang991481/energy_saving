#!/bin/bash
#

set -x

exec > >(sudo tee install.log)
exec 2>&1

echo "start installing....."
DIR=$(cd $(dirname "${BASH_SOURCE[0]}") && pwd)
source $DIR/install.conf

sudo apt-get update -y || exit 1
sudo apt-get install -y libmysqlclient-dev mysql-client mysql-server ntp ntpdate graphviz || exit 1
sudo apt-get install -y git python-pip python-setuptools python-tox python-dev gcc rabbitmq-server celeryd librabbitmq-dev openssl || exit 1
sudo apt-get install -y apache2 libapache2-mod-wsgi || exit 1

cd ${ENERGY_SAVING_DIR}

sudo pip install -r requirements.txt -r test-requirements.txt || exit 1
sudo python setup.py install || exit 1

sudo ntpdate $NTP_SERVERS
for NTP_SERVER in $NTP_SERVERS; do
    sed -i "/prepend customized ntp servers above/i \
server $NTP_SERVER iburst" /etc/ntp.conf
    sed -i "/prepend customized ntp servers above/i \
$NTP_SERVER" /etc/ntp/step-tickers
done
sudo systemctl enable ntp.service
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
    sudo mysqladmin -u ${MYSQL_USER} password ${MYSQL_PASSWORD}
    if [[ "$?" != "0" ]]; then
        echo "failed to setup initial mysql server password"
        exit 1
    else
        echo "mysql server password is initialized"
    fi
else
    echo "mysql serverpassword is updated"
fi
sudo mysql -u${MYSQL_USER} -p${MYSQL_PASSWORD} -e "show databases;"
if [[ "$?" != "0" ]]; then
    echo "mysql server password set failed"
    exit 1
else
    echo "mysql server password set succeeded"
fi
sudo mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "GRANT ALL ON *.* to '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}'; flush privileges;"
if [[ "$?" != "0" ]]; then
    echo "failed to update mysql server privileges to all"
    exit 1
    echo "mysql server privileges are updated"
fi
sudo mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "GRANT ALL ON *.* to '${MYSQL_USER}'@'${MYSQL_SERVER_IP}' IDENTIFIED BY '${MYSQL_PASSWORD}'; flush privileges;"
if [[ "$?" != "0" ]]; then
    echo "failed to update mysql server privileges to ${MYSQL_SERVER_IP}"
    exit 1
else
    echo "mysql server privileges are updated"
fi

sudo sudo mysql -h${MYSQL_SERVER_IP} --port=${MYSQL_SERVER_PORT} -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "drop database ${MYSQL_DATABASE};"
sudo sudo mysql -h${MYSQL_SERVER_IP} --port=${MYSQL_SERVER_PORT} -u ${MYSQL_USER} -p${MYSQL_PASSWORD} -e "create database ${MYSQL_DATABASE};"
if [[ "$?" != "0" ]]; then
    echo "mysql database set failed"
    exit 1
else
    echo "mysql database is set"
fi
sudo mkdir -p /var/log/energy_saving
sudo chmod 777 /var/log/energy_saving
sudo mkdir -p /var/www/energy_saving_web
sudo chmod 777 /var/www/energy_saving_web
sudo a2ensite energy-saving.conf

sudo energy-saving-db-manage revision -m"init" --autogenerate
sudo energy-saving-db-manage upgrade heads
if [[ "$?" != "0" ]]; then
    echo "failed to create db schema"
    exit 1
else
    echo "db schema is created"
fi
sudo systemctl daemon-reload

sudo systemctl enable apache2.service
sudo systemctl restart apache2.service
sudo systemctl status apache2.service
if [[ "$?" != "0" ]]; then
    echo "failed to restart apache2"
    exit 1
else
    echo "apache2 is restarted"
fi

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
