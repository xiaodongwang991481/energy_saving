import logging

from flask_admin.contrib.sqla import ModelView

from energy_saving.api import admin
from energy_saving.db import database
from energy_saving.db import models

logger = logging.getLogger(__name__)


def init():
    admin.add_view(
        ModelView(models.Datacenter, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.Sensor, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.Controller, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.SensorAttr, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.ControllerAttr, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.ControllerParam, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.EnvironmentSensor, database.SCOPED_SESSION())
    )
    admin.add_view(
        ModelView(models.EnvironmentSensorAttr, database.SCOPED_SESSION())
    )
