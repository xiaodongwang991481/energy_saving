"""Database model"""
import logging
from oslo_utils import uuidutils

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


class AttrMixin(object):
    type = Column(
        Enum('binary', 'continuous', 'integer', 'discrete'),
        default='continuous', server_default='continuous'
    )
    unit = Column(String(36))
    mean = Column(Float())
    deviation = Column(Float())
    max = Column(Float())
    min = Column(Float())
    differentiation_mean = Column(Float())
    differentiation_deviation = Column(Float())
    differentiation_max = Column(Float())
    differentiation_min = Column(Float())
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
    models = Column(JSON)
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
    energy_optimazation_target = relationship(
        'EnergyOptimazationTarget',
        foreign_keys='[EnergyOptimazationTarget.datacenter_name]',
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter', uselist=False),
        uselist=False
    )
    predictions = relationship(
        'Prediction',
        foreign_keys='[Prediction.datacenter_name]',
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
    attribute_data = relationship(
        'SensorAttrData',
        foreign_keys=(
            '[SensorAttrData.datacenter_name,'
            'SensorAttrData.sensor_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('sensor')
    )

    def __str__(self):
        return 'Sensor[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class SensorAttr(BASE, AttrMixin):
    """Sensor attribute table."""
    __tablename__ = 'sensor_attribute'
    datacenter_name = Column(
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
    )
    attribute_data = relationship(
        'SensorAttrData',
        foreign_keys=(
            '[SensorAttrData.datacenter_name,'
            'SensorAttrData.name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('attribute')
    )
    slo = relationship(
        'SensorAttrSLO',
        foreign_keys=(
            '[SensorAttrSLO.datacenter_name,'
            'SensorAttrSLO.sensor_attribute_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('attribute')
    )

    def __str__(self):
        return 'SensorAttr[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class SensorAttrSLO(BASE):
    """Sensor attribute slo."""
    __tablename__ = 'sensor_attribute_slo'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    sensor_attribute_name = Column(String(36), primary_key=True)
    min_threshold = Column(Float())
    max_threshold = Column(Float())
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'sensor_attribute_name'],
            ['sensor_attribute.datacenter_name', 'sensor_attribute.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return 'SensorAttrSLO[datacenter_name=%s,sensor_attribute_name=%s]' % (
            self.datacenter_name, self.sensor_attribute_name
        )


class SensorAttrData(BASE):
    """Sensor attribute data table."""
    __tablename__ = 'sensor_attribute_data'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    sensor_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'name'],
            [
                'sensor_attribute.datacenter_name',
                'sensor_attribute.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'sensor_name'],
            ['sensor.datacenter_name', 'sensor.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )
    sensor_attribute_predictions = relationship(
        'SensorAttrPrediction',
        foreign_keys=(
            '[SensorAttrPrediction.datacenter_name,'
            'SensorAttrPrediction.sensor_name,'
            'SensorAttrPrediction.sensor_attribute_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('datacenter')
    )

    def __str__(self):
        return (
            'SensorAttrData[datacenter_name=%s,'
            'sensor_name=%s,name=%s]'
        ) % (
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
    attribute_data = relationship(
        'ControllerAttrData',
        foreign_keys=(
            '[ControllerAttrData.datacenter_name,'
            'ControllerAttrData.controller_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('controller')
    )
    parameter_data = relationship(
        'ControllerParamData',
        foreign_keys=(
            '[ControllerParamData.datacenter_name,'
            'ControllerParamData.controller_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('controller')
    )

    def __str__(self):
        return 'Controller[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class ControllerAttr(BASE, AttrMixin):
    """controller attribute table."""
    __tablename__ = 'controller_attribute'
    datacenter_name = Column(
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
    )
    attribute_data = relationship(
        'ControllerAttrData',
        foreign_keys=(
            '[ControllerAttrData.datacenter_name,'
            'ControllerAttrData.name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('attribute')
    )

    def __str__(self):
        return (
            'ControllerAttr[datacenter_name=%s,name=%s]'
        ) % (
            self.datacenter_name, self.name
        )


class ControllerAttrData(BASE):
    """controller attribute data table."""
    __tablename__ = 'controller_attribute_data'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    controller_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'name'],
            [
                'controller_attribute.datacenter_name',
                'controller_attribute.name'
            ],
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
            'ControllerAttrData[datacenter_name=%s,'
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
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
    )
    parameter_data = relationship(
        'ControllerParamData',
        foreign_keys=(
            '[ControllerParamData.datacenter_name,'
            'ControllerParamData.name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('parameter')
    )

    def __str__(self):
        return (
            'ControllerParam[datacenter_name=%s,'
            'name=%s]'
        ) % (
            self.datacenter_name, self.name
        )


class ControllerParamData(BASE):
    """controller param data table."""
    __tablename__ = 'controller_parameter_data'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    controller_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'name'],
            [
                'controller_parameter.datacenter_name',
                'controller_parameter.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'controller_name'],
            ['controller.datacenter_name', 'controller.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )
    controller_parameter_predictions = relationship(
        'ControllerParamPrediction',
        foreign_keys=(
            '[ControllerParamPrediction.datacenter_name,'
            'ControllerParamPrediction.controller_name,'
            'ControllerParamPrediction.controller_parameter_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('controller_parameter')
    )

    def __str__(self):
        return (
            'ControllerParamData[datacenter_name=%s,'
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
    attribute_data = relationship(
        'EnvironmentSensorAttrData',
        foreign_keys=(
            '[EnvironmentSensorAttrData.datacenter_name,'
            'EnvironmentSensorAttrData.environment_sensor_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('environment_sensor')
    )

    def __str__(self):
        return 'EnvironmentSensor[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class EnvironmentSensorAttr(BASE, AttrMixin):
    """Environment sensor attribute table."""
    __tablename__ = 'environment_sensor_attribute'
    datacenter_name = Column(
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
    )
    attribute_data = relationship(
        'EnvironmentSensorAttrData',
        foreign_keys=(
            '[EnvironmentSensorAttrData.datacenter_name,'
            'EnvironmentSensorAttrData.name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('environment_sensor_attribute')
    )

    def __str__(self):
        return (
            'EnvironmentSensorAttr[datacenter_name=%s,'
            'name=%s]'
        ) % (
            self.datacenter_name, self.name
        )


class EnvironmentSensorAttrData(BASE):
    """Environment sensor attribute data table."""
    __tablename__ = 'environment_sensor_attribute_data'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    environment_sensor_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'name'],
            [
                'environment_sensor_attribute.datacenter_name',
                'environment_sensor_attribute.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'environment_sensor_name'],
            [
                'environment_sensor.datacenter_name',
                'environment_sensor.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'EnvironmentSensorAttrData[datacenter_name=%s,'
            'environment_sensor_name=%s,name=%s]'
        ) % (
            self.datacenter_name, self.environment_sensor_name, self.name
        )


class EnergyOptimazationTarget(BASE, AttrMixin):
    """Energy optimazation target table."""
    __tablename__ = 'energy_optimazation_target'
    datacenter_name = Column(
        String(36),
        ForeignKey('datacenter.name', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    properties = Column(JSON)
    energy_optimazation_target_data = relationship(
        'EnergyOptimazationTargetData',
        foreign_keys=(
            '[EnergyOptimazationTargetData.datacenter_name,'
            'EnergyOptimazationTargetData.energy_optimazation_target_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('energy_optimazation_target')
    )

    def __str__(self):
        return 'EnergyOptimazationTarget[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class EnergyOptimazationTargetData(BASE):
    """Energy optimazation target data table."""
    __tablename__ = 'energy_optimazation_target_data'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    energy_optimazation_target_name = Column(
        String(36),
        primary_key=True
    )
    name = Column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'energy_optimazation_target_name'],
            [
                'energy_optimazation_target.datacenter_name',
                'energy_optimazation_target.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
    )
    energy_optimazation_target_predictions = relationship(
        'EnergyOptimazationTargetPrediction',
        foreign_keys=(
            '[EnergyOptimazationTargetPrediction.datacenter_name,'
            'EnergyOptimazationTargetPrediction.'
            'energy_optimazation_target_name,'
            'EnergyOptimazationTargetPrediction.'
            'energy_optimazation_target_data_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('energy_optimazation_target_data')
    )

    def __str__(self):
        return 'EnergyOptimazationTargetData[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class Prediction(BASE):
    """Prediction table."""
    __tablename__ = 'prediction'
    datacenter_name = Column(
        String(36),
        ForeignKey('datacenter.name', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )
    name = Column(
        String(36),
        primary_key=True,
        default=uuidutils.generate_uuid
    )

    sensor_attribute_predictions = relationship(
        'SensorAttrPrediction',
        foreign_keys=(
            '[SensorAttrPrediction.datacenter_name,'
            'SensorAttrPrediction.prediction_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('prediction')
    )
    controller_parameter_predictions = relationship(
        'ControllerParamPrediction',
        foreign_keys=(
            '[ControllerParamPrediction.datacenter_name,'
            'ControllerParamPrediction.prediction_name]'
        ),
        passive_deletes=True,
        cascade='all, delete-orphan',
        backref=backref('prediction')
    )
    energy_optimazation_target_predications = relationship(
        'EnergyOptimazationTargetPrediction',
        foreign_keys=(
            '[EnergyOptimazationTargetPrediction.datacenter_name,'
            'EnergyOptimazationTargetPrediction.prediction_name]'
        ),
        cascade='all, delete-orphan',
        backref=backref('prediction')
    )

    def __str__(self):
        return 'Prediction[datacenter_name=%s,name=%s]' % (
            self.datacenter_name, self.name
        )


class SensorAttrPrediction(BASE):
    'sensor attribute prediction table.'
    __tablename__ = 'sensor_attribute_prediction'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    prediction_name = Column(
        String(36),
        primary_key=True
    )
    sensor_name = Column(
        String(36),
        primary_key=True
    )
    sensor_attribute_name = Column(
        String(36),
        primary_key=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'prediction_name'],
            [
                'prediction.datacenter_name',
                'prediction.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'sensor_name'],
            [
                'sensor.datacenter_name',
                'sensor.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'sensor_attribute_name'],
            [
                'sensor_attribute.datacenter_name',
                'sensor_attribute.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'sensor_name', 'sensor_attribute_name'],
            [
                'sensor_attribute_data.datacenter_name',
                'sensor_attribute_data.sensor_name',
                'sensor_attribute_data.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'SensorAttrPrediction[datacenter_name=%s,'
            'prediction_name=%s,sensor_name=%s,sensor_attribute_name=%s]' % (
                self.datacenter_name, self.prediction_name,
                self.sensor_name, self.sensor_attribute_name
            )
        )


class ControllerParamPrediction(BASE):
    'controller parameter prediction table.'
    __tablename__ = 'controller_parameter_prediction'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    prediction_name = Column(
        String(36),
        primary_key=True
    )
    controller_name = Column(
        String(36),
        primary_key=True
    )
    controller_parameter_name = Column(
        String(36),
        primary_key=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'prediction_name'],
            [
                'prediction.datacenter_name',
                'prediction.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'controller_name'],
            [
                'controller.datacenter_name',
                'controller.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'controller_parameter_name'],
            [
                'controller_parameter.datacenter_name',
                'controller_parameter.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            [
                'datacenter_name', 'controller_name',
                'controller_parameter_name'
            ],
            [
                'controller_parameter_data.datacenter_name',
                'controller_parameter_data.controller_name',
                'controller_parameter_data.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'ControllerParamPrediction[datacenter_name=%s,'
            'prediction_name=%s,controller_name=%s,'
            'controller_parameter_name=%s]' % (
                self.datacenter_name, self.prediction_name,
                self.controller_name, self.controller_parameter_name
            )
        )


class EnergyOptimazationTargetPrediction(BASE):
    'energy optimazation target prediction table.'
    __tablename__ = 'energy_optimazation_target_prediction'
    datacenter_name = Column(
        String(36),
        primary_key=True
    )
    prediction_name = Column(
        String(36),
        primary_key=True
    )
    energy_optimazation_target_name = Column(
        String(36),
        primary_key=True
    )
    energy_optimazation_target_data_name = Column(
        String(36),
        primary_key=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ['datacenter_name'],
            ['datacenter.name'],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'prediction_name'],
            [
                'prediction.datacenter_name',
                'prediction.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ['datacenter_name', 'energy_optimazation_target_name'],
            [
                'energy_optimazation_target.datacenter_name',
                'energy_optimazation_target.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            [
                'datacenter_name', 'energy_optimazation_target_name',
                'energy_optimazation_target_data_name'
            ],
            [
                'energy_optimazation_target_data.datacenter_name',
                'energy_optimazation_target_data.'
                'energy_optimazation_target_name',
                'energy_optimazation_target_data.name'
            ],
            onupdate="CASCADE", ondelete="CASCADE"
        )
    )

    def __str__(self):
        return (
            'EnergyOptimazationTargetPrediction[datacenter_name=%s,'
            'prediction_name=%s,energy_optimazation_target_name=%s,'
            'energy_optimazation_target_data_name=%s]' % (
                self.datacenter_name, self.prediction_name,
                self.energy_optimazation_target_name,
                self.energy_optimazation_target_data_name
            )
        )
