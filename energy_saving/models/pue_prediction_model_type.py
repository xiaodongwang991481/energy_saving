import logging
import pandas
import six

from energy_saving.db import database
from energy_saving.db import models
from energy_saving.models import base_model_type


logger = logging.getLogger(__name__)


class PUEPredictionModelType(base_model_type.BaseModelType):
    def get_metadata(self, datacenter):
        metadata = {}
        with database.session() as session:
            result = session.query(models.Datacenter).filter_by(
                name=datacenter
            ).one()
            metadata[
                'controller_attribute'
            ] = database.get_datacenter_device_type_metadata(
                result, 'controller_attribute'
            )
        return metadata

    def get_data(self, datacenter, metadata):
        dataframe = {}
        with database.influx_session() as session:
            controller_attributes = metadata['controller_attribute']
            for measurement, attribute in six.iteritems(
                    controller_attributes
            ):
                for controller in six.iteritems(attribute['devices']):
                    result = session.query(
                        "select value from %s where datacenter='%s' "
                        "and device_type='controller_attribute' "
                        "and device='%s'order by time" % (
                            datacenter, controller
                        ),
                        epoch='s'
                    )
                    values = []
                    times = []
                    for item in result.get_points():
                        values.append(item['value'])
                        times.append(item['time'])
                    dataframe[
                        '%s.%s' % (measurement, controller)
                    ] = pandas.Series(values, index=times)
        return pandas.DataFrame(dataframe)
