import logging
import six

from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.contrib.sqla.fields import QuerySelectField
from flask_admin.contrib.sqla.form import AdminModelConverter
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from flask_admin.model.fields import AjaxSelectField

from energy_saving.api import admin
from energy_saving.db import database
from energy_saving.db import models
from energy_saving.models import base_model_type_builder


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
    form_base_class = SecureForm
    column_display_pk = True
    can_export = True
    model_form_converter = ForeignKeyModelConverter

    def __init__(self, model, session, *args, **kwargs):
        self.column_list = model.__table__.columns.keys()
        self.column_labels = {
            name: column.name
            for name, column in six.iteritems(dict(model.__table__.columns))
        }
        self.form_columns = model.__table__.columns.keys()
        self.column_export_list = model.__table__.columns.keys()
        super(BaseModelView, self).__init__(model, session, *args, **kwargs)


def init():
    for model_name, model in six.iteritems(MODELS):
        logger.debug('add model %s view %s', model_name, model)
        admin.add_view(
            BaseModelView(model, database.SCOPED_SESSION())
        )
    admin.add_view(
        FileAdmin(
            base_model_type_builder.CONF.model_dir,
            '/static/', name='Model Files'
        )
    )
