"""Database model"""
import logging

from oslo_utils import uuidutils

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import JSON
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
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    name = Column(
        String(36)
    )
    location = Column(JSON)
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


class Sensor(BASE, LocationMixin):
    """Sensor table."""
    __tablename__ = 'sensor'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    datacenter_id = Column(
        String(36),
        ForeignKey('datacenter.id', onupdate='RESTRICT', ondelete='CASCADE')
    )
    name = Column(String(36))
    properties = Column(JSON)


class SensorAttr(BASE, SensorMixin):
    """Sensor attribute table."""
    __tablename__ = 'sensor_attribute'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    sensor_id = Column(
        String(36),
        ForeignKey('sensor.id', onupdate='RESTRICT', ondelete='CASCADE')
    )
    name = Column(String(36))


class Controller(BASE, LocationMixin):
    """controller table."""
    __tablename__ = 'controller'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    datacenter_id = Column(
        String(36),
        ForeignKey('datacenter.id', onupdate='RESTRICT', ondelete='CASCADE')
    )
    name = Column(String(36))
    properties = Column(JSON)


class ControllerAttr(BASE, SensorMixin):
    """controller attribute table."""
    __tablename__ = 'controller_attribute'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    controller_id = Column(
        String(36),
        ForeignKey('controller.id', onupdate='RESTRICT', ondelete='CASCADE')
    )
    name = Column(String(36))


class ControllerParam(BASE, ParamMixin):
    """controller param table."""
    __tablename__ = 'controller_parameter'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    controller_id = Column(
        String(36),
        ForeignKey('controller.id', onupdate='RESTRICT', ondelete='CASCADE')
    )
    name = Column(String(36))


class EnvironmentSensor(BASE, LocationMixin):
    """Environment sensor table."""
    __tablename__ = 'environment_sensor'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    datacenter_id = Column(
        String(36),
        ForeignKey('datacenter.id', onupdate='RESTRICT', ondelete='CASCADE')
    )
    name = Column(String(36))
    properties = Column(JSON)


class EnvironmentSensorAttr(BASE, SensorMixin):
    """Environment sensor attribute table."""
    __tablename__ = 'environment_sensor_attribute'
    id = Column(
        String(36), primary_key=True,
        default=uuidutils.generate_uuid
    )
    controller_id = Column(
        String(36),
        ForeignKey(
            'environment_sensor.id', onupdate='RESTRICT', ondelete='CASCADE'
        )
    )
    name = Column(String(36))
