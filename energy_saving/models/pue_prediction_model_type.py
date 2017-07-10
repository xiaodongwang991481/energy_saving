import logging
import pandas
import six

from energy_saving.db import database
from energy_saving.db import models
from energy_saving.models import base_model_type


logger = logging.getLogger(__name__)


class PUEPredictionModelType(base_model_type.BaseModelType):
    def get_metadata(datacenter):
        metadata = {}
        with database.session() as session:
            result = session.query(models.Datacenter).filter_by(
                name=datacenter
            ).one()
            for parameter in result.controller_parameters:
                controller_parameters = metadata.setdefault(
                    'controller_parameter', {}
                )
                parameter = controller_parameters[parameter.name] = {}
                for data in parameter.parameter_data:
                    parameter[data.controller_name] = {}
        return metadata

    def get_data(datacenter, metadata):
        dataframe = {}
        with database.influx_session() as session:
            for key, controller_parameters in six.iteritems(metadata):
                for measurement, parameter in six.iteritems(
                    controller_parameters
                ):
                    for controller, value in six.iteritems(parameter):
                        result = session.query(
                            "select value from %s where datacenter='%s' "
                            "and device_type='controller' "
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
                            '%s.%s.%s' % (measurement, controller, key)
                        ] = pandas.Series(values, index=times)
        return pandas.DataFrame(dataframe)
