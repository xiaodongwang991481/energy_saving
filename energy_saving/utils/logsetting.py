"""Module to setup logging configuration.

   .. moduleauthor:: Xiaodong Wang <xiaodongwang@huawei.com>
"""
import logging
import logging.handlers
import os
import os.path
from oslo_config import cfg
import sys

from energy_saving.utils import settings


opts = [
    cfg.StrOpt('loglevel',
               help='logging level',
               default=settings.DEFAULT_LOGLEVEL),
    cfg.StrOpt('logdir',
               help='logging directory',
               default=settings.DEFAULT_LOGDIR),
    cfg.IntOpt('log_interval',
               help='log interval',
               default=settings.DEFAULT_LOGINTERVAL),
    cfg.StrOpt('log_interval_unit',
               help='log interval unit',
               default=settings.DEFAULT_LOGINTERVAL_UNIT),
    cfg.StrOpt('log_format',
               help='log format',
               default=settings.DEFAULT_LOGFORMAT),
    cfg.IntOpt('log_backup_count',
               help='log backup count',
               default=settings.DEFAULT_LOGBACKUPCOUNT)
]
CONF = cfg.CONF
CONF.register_opts(opts)

# mapping str setting in flag --loglevel to logging level.
LOGLEVEL_MAPPING = {
    'finest': logging.DEBUG - 2,  # more detailed log.
    'fine': logging.DEBUG - 1,    # detailed log.
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}


logging.addLevelName(LOGLEVEL_MAPPING['fine'], 'fine')
logging.addLevelName(LOGLEVEL_MAPPING['finest'], 'finest')


# disable logging when logsetting.init not called
logging.getLogger().setLevel(logging.CRITICAL)


def getLevelByName(level_name):
    """Get log level by level name."""
    return LOGLEVEL_MAPPING[level_name]


def init(logfile):
    """Init loggsetting. It should be called after flags.init."""
    loglevel = CONF.loglevel.lower()
    logdir = CONF.logdir
    logger = logging.getLogger()
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    if logdir:
        if not logfile:
            logfile = '%s.log' % os.path.basename(sys.argv[0])

        handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(logdir, logfile),
            when=CONF.log_interval_unit,
            interval=CONF.log_interval,
            backupCount=CONF.log_backup_count)
    else:
        if not logfile:
            handler = logging.StreamHandler(sys.stderr)
        else:
            handler = logging.handlers.TimedRotatingFileHandler(
                logfile,
                when=CONF.log_interval_unit,
                interval=CONF.log_interval,
                backupCount=CONF.log_backup_count)

    if loglevel in LOGLEVEL_MAPPING:
        logger.setLevel(LOGLEVEL_MAPPING[loglevel])
        handler.setLevel(LOGLEVEL_MAPPING[loglevel])

    formatter = logging.Formatter(
        CONF.log_format)

    handler.setFormatter(formatter)
    logger.addHandler(handler)
