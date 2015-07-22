from django.db import models
from django.conf import settings
import celery
import threading
import psutil

import helpers


class Tileset(models.Model):

    # base
    name = models.CharField(unique=True, max_length=30)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # server
    server_url = models.URLField()
    server_service_type = models.CharField(max_length=10)
    server_username = models.CharField(blank=True, max_length=30)
    server_password = models.CharField(blank=True, max_length=30)

    # layer
    layer_name = models.CharField(blank=True, max_length=200)
    layer_zoom_start = models.IntegerField(blank=True, default=0)
    layer_zoom_stop = models.IntegerField()

    # region
    geom = models.TextField(blank=True)

    # size of the tileset after /generate is invoked. /status will return the size of the file on disk and
    # actual last modified date of file at teh time of request.
    filesize = models.BigIntegerField(editable=False, default=0)

    # 'not generated', 'in progress', 'ready'
    # status = models.CharField(editable=False, default='not generated')

    def __unicode__(self):
        return self.name

    # terminate the seeding of this tileset!
    def stop(self):
        print '---- tileset.stop'
        res = {'status': 'not in progress'}
        with helpers.tasks_lock:
            pid = helpers.tasks_dict.get(self.id, None)
            if pid:
                print '---- tileset.stop, will stop, pid: {}'.format(pid)
                res = {'status': 'stopped'}
                helpers.tasks_dict[self.id] = None
                if pid != 'preparing_to_start':
                    process = psutil.Process(pid=pid)
                    if process:
                        children = process.children()
                        for c in children:
                            c.terminate()
                        process.terminate()
                else:
                    res = {'status': 'debug, prevernted started!'}
            else:
                print '---- tileset.stop, will NOT stop. not running'

        return res

    # use the tileset object as input to start creation of the mbtiles
    def generate(self):
        print '---- tileset.generate'
        with helpers.tasks_lock:
            pid = helpers.tasks_dict.get(self.id, None)

            if not pid:
                print '---- tileset.generate, will generate'
                # set the pid to 'preparing_to_start' when we start the thread. When process starts, it will update it
                # to be the actual pid
                helpers.tasks_dict[self.id] = 'preparing_to_start'
                helpers.seed_process_db_connection(self)
                res = {'status': 'started'}
            else:
                print '---- tileset.generate, will NOT generate. already running, pid: {}'.format(pid)
                res = {'status': 'already started'}
            return res

    # TODO: the the log for the mbtiles being generated should be seperate from the log for the last successfully downloaded
    #       file.
    def status(self):
        return helpers.get_status(self)
