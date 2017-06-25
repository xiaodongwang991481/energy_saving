import os
import sys

from alembic import command as alembic_command
from alembic import config as alembic_config
from alembic import environment
from alembic import script as alembic_script
from alembic import util as alembic_util
import six

from oslo_config import cfg

from energy_saving.db import database
from energy_saving.utils import logsetting
from energy_saving.utils import settings


HEAD_FILENAME = 'HEAD'
HEADS_FILENAME = 'HEADS'
MIGRATION_DIR = os.path.join(
    os.path.dirname(__file__), 'alembic_migrations'
)
alembic_ini = os.path.join(
    os.path.dirname(__file__), 'alembic.ini'
)
CONF = cfg.CONF
opts = [
    cfg.StrOpt('logfile',
               help='log file name',
               default=settings.DB_MANAGE_LOGFILE)
]
CONF.register_opts(opts)


def add_alembic_subparser(sub, cmd):
    return sub.add_parser(cmd, help=getattr(alembic_command, cmd).__doc__)


def add_command_parsers(subparsers):
    for name in ['current', 'history', 'heads']:
        parser = add_alembic_subparser(subparsers, name)
        parser.set_defaults(func=do_generic_show)
        parser.add_argument('--verbose',
                            action='store_true',
                            help='Display more verbose output for the '
                                 'specified command')

    help_text = (getattr(alembic_command, 'branches').__doc__ +
                 ' and validate head file')
    parser = subparsers.add_parser('check_migration', help=help_text)
    parser.set_defaults(func=do_check_migration)

    parser = add_alembic_subparser(subparsers, 'upgrade')
    parser.add_argument('--delta', type=int)
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('revision', nargs='?')
    parser.set_defaults(func=do_upgrade)

    parser = subparsers.add_parser('downgrade', help="(No longer supported)")
    parser.add_argument('None', nargs='?', help="Downgrade not supported")
    parser.set_defaults(func=no_downgrade)

    parser = add_alembic_subparser(subparsers, 'stamp')
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('revision')
    parser.set_defaults(func=do_stamp)

    parser = add_alembic_subparser(subparsers, 'revision')
    parser.add_argument('-m', '--message')
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('--autogenerate', action='store_true')
    parser.set_defaults(func=do_revision)


command_opt = cfg.SubCommandOpt('command',
                                title='Command',
                                help='Available commands',
                                handler=add_command_parsers)
CONF.register_cli_opt(command_opt)


def do_alembic_command(config, cmd, revision=None, desc=None, **kwargs):
    args = []
    if revision:
        args.append(revision)

    if desc:
        alembic_util.msg(
            'Running %(cmd)s (%(desc)s)...' % {'cmd': cmd, 'desc': desc}
        )
    else:
        alembic_util.msg(
            'Running %(cmd)s ...' % {'cmd': cmd}
        )
    try:
        getattr(alembic_command, cmd)(config, *args, **kwargs)
    except alembic_util.CommandError as e:
        alembic_util.err(six.text_type(e))
    alembic_util.msg('OK')


def do_generic_show(config, cmd):
    kwargs = {'verbose': CONF.command.verbose}
    do_alembic_command(config, cmd, **kwargs)


def do_check_migration(config, cmd):
    do_alembic_command(config, 'heads')
    validate_head_files(config)


def do_upgrade(config, cmd):
    if not CONF.command.revision and not CONF.command.delta:
        raise SystemExit('You must provide a revision or relative delta')
    else:
        revision = CONF.command.revision or ''
        if '-' in revision:
            raise SystemExit(
                'Negative relative revision (downgrade) not supported'
            )
        delta = CONF.command.delta
        if delta:
            if '+' in revision:
                raise SystemExit(
                    'Use either --delta or relative revision, not both'
                )
            if delta < 0:
                raise SystemExit('Negative delta (downgrade) not supported')
            revision = '%s+%d' % (revision, delta)

        if revision == 'head':
            revision = 'heads'
        if not CONF.command.sql:
            run_sanity_checks(config, revision)
        do_alembic_command(
            config, cmd, revision=revision,
            sql=CONF.command.sql
        )


def no_downgrade(config, cmd):
    raise SystemExit("Downgrade no longer supported")


def do_stamp(config, cmd):
    do_alembic_command(config, cmd,
                       revision=CONF.command.revision,
                       sql=CONF.command.sql)


def do_revision(config, cmd):
    kwargs = {
        'message': CONF.command.message,
        'autogenerate': CONF.command.autogenerate,
        'sql': CONF.command.sql,
    }
    do_alembic_command(config, cmd, **kwargs)
    update_head_files(config)


def _check_head(head_file, head):
    try:
        with open(head_file) as file_:
            observed_head = file_.read().strip()
    except IOError:
        pass
    else:
        if observed_head != head:
            alembic_util.err(
                'HEAD file does not match migration timeline '
                'head, expected: %(head)s' % {'head': head}
            )


def validate_head_files(config):
    '''Check that HEAD files contain the latest head for the branch.'''
    head_file = _get_head_file_path(config)
    heads_file = _get_heads_file_path(config)
    if not os.path.exists(head_file) and not os.path.exists(heads_file):
        alembic_util.err("Repository does not contain HEAD files")
        return
    heads = _get_heads(config)
    for file_ in (head_file, heads_file):
        if os.path.exists(file_):
            if not heads:
                alembic_util.err(
                    'HEAD file contains no head'
                )
            if len(heads) > 1:
                alembic_util.err(
                    'HEAD file contains more than one head: %(heads)s' % {
                        'heads': heads
                    }
                )
            for head in heads:
                _check_head(file_, head)


def _get_heads(config):
    script = alembic_script.ScriptDirectory.from_config(config)
    return script.get_heads()


def update_head_files(config):
    '''Update HEAD files with the latest branch heads.'''
    heads = _get_heads(config)
    old_head_file = _get_head_file_path(config)
    old_heads_file = _get_heads_file_path(config)
    for file_ in (old_head_file, old_heads_file):
        with open(file_, 'w+') as f:
            for head in heads:
                f.write(head + '\n')


def _get_root_versions_dir(config):
    '''Return root directory that contains all migration rules.'''
    return os.path.join(MIGRATION_DIR, 'versions')


def _get_head_file_path(config):
    '''Return the path of the file that contains single head.'''
    return os.path.join(
        _get_root_versions_dir(config),
        HEAD_FILENAME)


def _get_heads_file_path(config):
    return os.path.join(
        _get_root_versions_dir(config),
        HEADS_FILENAME)


def _set_version_locations(config):
    '''Make alembic see all revisions in all migration branches.'''
    version_paths = [_get_root_versions_dir(config)]
    config.set_main_option('version_locations', ' '.join(version_paths))


def get_alembic_config():
    config = alembic_config.Config(alembic_ini)
    config.set_main_option(
        'script_location',
        MIGRATION_DIR
    )
    config.set_main_option('sqlalchemy.url', settings.DATABASE_URI)
    _set_version_locations(config)
    return config


def run_sanity_checks(config, revision):
    script_dir = alembic_script.ScriptDirectory.from_config(config)

    def check_sanity(rev, context):
        # TODO(ihrachyshka): here we use internal API for alembic; we may need
        # alembic to expose implicit_base= argument into public
        # iterate_revisions() call
        for script in script_dir.revision_map.iterate_revisions(
                revision, rev, implicit_base=True):
            if hasattr(script.module, 'check_sanity'):
                script.module.check_sanity(context.connection)
        return []

    with environment.EnvironmentContext(config, script_dir,
                                        fn=check_sanity,
                                        starting_rev=None,
                                        destination_rev=revision):
        script_dir.run_env()


def main():
    CONF(sys.argv[1:])
    logsetting.init(CONF.logfile)
    database.init()
    config = get_alembic_config()
    return CONF.command.func(config, CONF.command.name)
