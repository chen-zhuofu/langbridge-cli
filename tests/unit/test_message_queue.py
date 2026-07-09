from langbridge_code.ui.message_queue import QueuedMessage, UserMessageQueue


def test_enqueue_dequeue_fifo():
    queue = UserMessageQueue(max_size=3)
    assert queue.enqueue("first", turn_id=1)
    assert queue.enqueue("second", turn_id=2)
    assert len(queue) == 2
    assert queue.dequeue() == QueuedMessage(text="first", turn_id=1)
    assert queue.dequeue() == QueuedMessage(text="second", turn_id=2)
    assert queue.dequeue() is None


def test_enqueue_rejects_empty_and_when_full():
    queue = UserMessageQueue(max_size=2)
    assert not queue.enqueue("", turn_id=1)
    assert queue.enqueue("one", turn_id=1)
    assert queue.enqueue("two", turn_id=2)
    assert not queue.enqueue("three", turn_id=3)
    assert queue.full


def test_clear_returns_count():
    queue = UserMessageQueue()
    queue.enqueue("a", turn_id=1)
    queue.enqueue("b", turn_id=2)
    assert queue.clear() == 2
    assert len(queue) == 0


def test_items_snapshot():
    queue = UserMessageQueue()
    queue.enqueue("alpha", turn_id=1)
    queue.enqueue("beta", turn_id=2)
    assert queue.items() == [
        QueuedMessage(text="alpha", turn_id=1),
        QueuedMessage(text="beta", turn_id=2),
    ]
    queue.dequeue()
    assert queue.items() == [QueuedMessage(text="beta", turn_id=2)]
