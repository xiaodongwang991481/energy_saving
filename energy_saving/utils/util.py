import logging
import sys

from oslo_config import cfg

from energy_saving.utils import settings


CONF = cfg.ConfigOpts()
logger = logging.getLogger(__name__)


def init(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    CONF(
        argv,
        'energy_saving',
        default_config_dirs=[settings.CONFIG_DIR]
    )
