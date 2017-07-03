"""Database model"""
import logging

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import JSON
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy import String


BASE = declarative_base()
logger = logging.getLogger(__name__)


class LocationMixin(object):
    location = Column(JSON)


class SensorMixin(object):
    type = Column(
        Enum('binary', 'continuous', 'integer', 'discrete'),
        default='continuous', server_default='continuous'
    )
    unit = Column(String(36))
    mean = Column(Float())
    deviation = Column(Float())
    max = Column(Float())
    min = Column(Float())
    possible_values = Column(JSON)


class ParamMixin(object):
    type = Column(
        Enum('binary', 'continuous', 'integer', 'discrete'),
        default='continuous', server_default='continuous'
    )
    unit = Column(String(36))
    max = Column(Float())
    min = Column(Float())
    possible_values = Column(JSON)


class Datacenter(BASE, LocationMixin):
    """Datacenter table."""
    __tablename__ = 'datacenter'
    name = Column(
        String(36), primary_key=True
    )
    type = Column(
        Enum('production', 'lab'), default='produdction',
        server_default='production'
    )
    properties = Column(JSON)
    sensor_attributes_prediction_model = Column(String(36))
    controller_attributes_prediction_model = Column(String(36))
    pue_prediction_model = Column(String(36))
    best_controller_params_model = Column(String(36))
    decision_model = Column(String(36))
    sensors = relationship(
        'Sensor',
        foreign_keys='[Sensor.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )
    sensor_attributes = relationship(
        'SensorAttr',
        foreign_keys='[SensorAttr.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )
    controllers = relationship(
        'Controller',
        foreign_keys='[Controller.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )
    controller_attributes = relationship(
        'ControllerAttr',
        foreign_keys='[ControllerAttr.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )
    controller_parameters = relationship(
        'ControllerParam',
        foreign_keys='[ControllerParam.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )
    environment_sensors = relationship(
        'EnvironmentSensor',
        foreign_keys='[EnvironmentSensor.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )
    environment_sensor_attributes = relationship(
        'EnvironmentSensorAttr',
        foreign_keys='[EnvironmentSensorAttr.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )

    def __str__(self):
        return 'Datacenter{name=%s}' % self.name


class Sensor(BASE, LocationMixin):
    """Sensor table."""
    __tablename__ = 'sensor'
    datacenter_name = Column(
        String(36),
        ForeignKey(
            'datacenter.name',
            onupdate='CASCADE', ondelete='CASCADE'
        ),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    attributes = relationship(
        'SensorAttr',
        foreign_keys='[SensorAttr.datacenter_name,SensorAttr.name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('sensor')
    )

    def __str__(self):
        return 'Sensor[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class SensorAttr(BASE, SensorMixin):
    """Sensor attribute table."""
    __tablename__ = 'sensor_attribute'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    sensor_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'sensor_name'],
            ['sensor.datacenter_name', 'sensor.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return 'SensorAttr[datacenter_name=%s,sensor_name=%s,name=%s]' % (
            self.datacenter_name, self.sensor_name, self.name
        )


class Controller(BASE, LocationMixin):
    """controller table."""
    __tablename__ = 'controller'
    datacenter_name = Column(
        String(36),
        ForeignKey('datacenter.name', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    attributes = relationship(
        'ControllerAttr',
        foreign_keys=(
            '[ControllerAttr.datacenter_name,'
            'ControllerAttr.controller_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('controller')
    )
    parameters = relationship(
        'ControllerParam',
        foreign_keys=(
            '[ControllerParam.datacenter_name,'
            'ControllerParam.controller_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('controller')
    )

    def __str__(self):
        return 'Controller[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class ControllerAttr(BASE, SensorMixin):
    """controller attribute table."""
    __tablename__ = 'controller_attribute'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    controller_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'controller_name'],
            ['controller.datacenter_name', 'controller.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'ControllerAttr[datacenter_name=%s,'
            'controller_name=%s,name=%s]'
        ) % (
            self.datacenter_name, self.controller_name, self.name
        )


class ControllerParam(BASE, ParamMixin):
    """controller param table."""
    __tablename__ = 'controller_parameter'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    controller_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'controller_name'],
            ['controller.datacenter_name', 'controller.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'ControllerParam[datacenter_name=%s,'
            'controller_name=%s,name=%s]'
        ) % (
            self.datacenter_name, self.controller_name, self.name
        )


class EnvironmentSensor(BASE, LocationMixin):
    """Environment sensor table."""
    __tablename__ = 'environment_sensor'
    datacenter_name = Column(
        String(36),
        ForeignKey('datacenter.name', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    attributes = relationship(
        'EnvironmentSensorAttr',
        foreign_keys=(
            '[EnvironmentSensorAttr.datacenter_name,'
            'EnvironmentSensorAttr.environment_sensor_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('environment_sensor')
    )

    def __str__(self):
        return 'EnvironmentSensor[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class EnvironmentSensorAttr(BASE, SensorMixin):
    """Environment sensor attribute table."""
    __tablename__ = 'environment_sensor_attribute'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    environment_sensor_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'environment_sensor_name'],
            ['environment_sensor.datacenter_name', 'environment_sensor.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'EnvironmentSensorAttr[datacenter_name=%s,'
            'environment_sensor_name=%s,name=%s]'
        ) % (
            self.datacenter_name, self.environment_sensor_name, self.name
        )
