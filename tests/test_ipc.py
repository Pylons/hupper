import queue

from hupper.ipc import Pipe, spawn


def echo(pipe):
    q = queue.Queue()
    pipe.activate(q.put)
    msg = q.get()
    while msg is not None:
        pipe.send(msg)
        msg = q.get()
    pipe.close()


def test_ipc_close():
    c1, c2 = Pipe()
    c1_q = queue.Queue()
    c1.activate(c1_q.put)

    with spawn(
        __name__ + '.echo',
        kwargs={"pipe": c2},
        pass_fds=[c2.r_fd, c2.w_fd],
    ) as proc:
        try:
            c2.close()

            c1.send("hello world")
            assert c1_q.get() == "hello world"

            c1.close()
        finally:
            proc.terminate()
