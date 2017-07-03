import logging

from flask_admin.contrib.sqla.fields import QuerySelectField
from flask_admin.contrib.sqla.form import AdminModelConverter
from flask_admin.contrib.sqla import ModelView
from flask_admin.model.fields import AjaxSelectField

from energy_saving.api import admin
from energy_saving.db import database
from energy_saving.db import models

logger = logging.getLogger(__name__)
MODELS = {
    clazz.__tablename__: clazz
    for clazz in models.BASE._decl_class_registry.values()
    if isinstance(clazz, type) and issubclass(clazz, models.BASE)
}


class ForeignKeyModelConverter(AdminModelConverter):
    def get_converter(self, column):
        for foreign_key in column.foreign_keys:
            return self.convert_foreign_key
        return super(ForeignKeyModelConverter, self).get_converter(column)

    def convert_foreign_key(self, column, field_args, **extra):
        loader = getattr(self.view, '_form_ajax_refs', {}).get(column.name)
        if loader:
            return AjaxSelectField(loader, **field_args)
        if 'query_factory' not in field_args:
            remote_model = None
            remote_column = None
            for foreign_key in column.foreign_keys:
                remote_column = foreign_key.column
                remote_model = MODELS[remote_column.table.fullname]
            field_args['query_factory'] = (
                lambda: [
                    getattr(obj, remote_column.name)
                    for obj in self.session.query(remote_model).all()
                ]
            )
            field_args['get_pk'] = lambda obj: obj
            field_args['get_label'] = lambda obj: obj
        return QuerySelectField(**field_args)


class BaseModelView(ModelView):
    column_display_pk = True
    can_export = True
    model_form_converter = ForeignKeyModelConverter

    def __init__(self, model, session, *args, **kwargs):
        self.column_list = [
            column.name for column in model.__table__.columns
        ]
        self.column_labels = {
            column.name: column.name for column in model.__table__.columns
        }
        self.form_columns = [
            column.name for column in model.__table__.columns
        ]
        self.column_export_list = [
            column.name for column in model.__table__.columns
        ]
        super(BaseModelView, self).__init__(model, session, *args, **kwargs)


def init():
    admin.add_view(
        BaseModelView(models.Datacenter, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.Sensor, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.Controller, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.SensorAttr, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.ControllerAttr, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.ControllerParam, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.EnvironmentSensor, database.SCOPED_SESSION())
    )
    admin.add_view(
        BaseModelView(models.EnvironmentSensorAttr, database.SCOPED_SESSION())
    )
