import functools
import redis,rq

@functools.lru_cache()
def conn():
    return redis.Redis()

class QueueRunner:
    def __init__(self, qname, **kwargs):
        self.redis = redis.Redis()
        self.queue = rq.Queue(qname, connection=self.redis, **kwargs)

    # Timeout includes time waiting in the queue; so it needs to be as long as the longest job we MIGHT run.
    def run(self, func, *args, timeout=3*3600, at_front=False, **kwargs):
        print('func = ', func)
#        kw = dict(kwargs)
#        kw['timeout'] = timeout
        job = rq.job.Job.create(func, connection=self.redis, timeout=timeout, args=args, kwargs=kwargs)
        #job = self.queue.enqueue(*args, **kwargs)
        self.queue.enqueue_job(job, at_front=at_front)
        try:
            result = rq.results.Result.fetch_latest(job, serializer=job.serializer, timeout=timeout)
            if result.type == result.Type.SUCCESSFUL: 
                ret = result.return_value
                print('Success ', ret)
                return ret
            else: 
                print('Failure ', result.exc_string)
                raise RuntimeError(result.exc_string)

        except:
            print('Canceling...')
            try:
                rq.command.send_stop_job_command(self.redis, job.id)
            except Exception as e:
                print('Exception stopping job ', e)
                # Job is not currently executing, No such job
                pass
            try:
                job.cancel()
            except Exception as e:
                print('Exception canceling job ', e)

            try:
                job.delete()
            except Exception as e:
                print('Exception deleting job ', e)

            raise

# One queue per licensed piece of software
_queues = {qname: (lambda: QueueRunner('q_'+qname)) for qname in ('arcgis', 'ecognition', 'idl')}
_queue_names = {_queues.keys()}

@functools.lru_cache()
def queue(qname):
    return _queues[qname]()

#def run_remote_queued(qname, *args, **kwargs):
#    return queues[qname].run(run_remote, *args, **kwargs)


# ==============================================================================

def blocking_lock(lname, sleep=5, timeout=3*3600):
    # https://redis-py.readthedocs.io/en/v5.0.1/connections.html
    assert lname in _queue_names
    return conn().lock('l_'+lname, timeout=timeout)

def clear_locks():
    rd = conn()
    for lname in _queue_names:
        rd.delete('l_'+lname)
