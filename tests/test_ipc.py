import queue

from hupper.ipc import Pipe


def test_ipc_close():
    c1, c2 = Pipe()
    c1_q = queue.Queue()
    c2_q = queue.Queue()
    c1.activate(c1_q.put)
    c2.activate(c2_q.put)

    c1.send("hello")
    c2.send("world")
    assert c2_q.get() == "hello"
    assert c1_q.get() == "world"

    c1.close()
    c2.close()
    c1.reader_thread.join()
    c2.reader_thread.join()
