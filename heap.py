# Pairing heap-based priority queue/min-heap implementation.
# Copyright (c) 2012 Lars Buitinck.

from collections import namedtuple
from functools import reduce


class Heap(object):
    """Min-heap.

    Objects that have been inserted using push can be retrieved in sorted
    order by repeated use of pop or pop_safe.
    """

    __slots__ = ["_root", "_nelems"]

    def __init__(self, items=()):
        self._root = None
        self._nelems = 0

        for x in items:
            self.push(x)

    def __iadd__(self, other):
        """Merge other into self, destroying other in the process."""

        self._root = _meld(self._root, other._root)
        self._nelems += other._nelems

        other._root = None
        other._nelems = 0

        return self

    def __len__(self):
        return self._nelems

    def _pop(self):
        r = self._root.key
        self._root = _pair(self._root.sub)
        self._nelems -= 1
        return r

    def pop(self):
        """Remove the smallest element from the heap and return it.

        Raises IndexError when the heap is empty.
        """
        try:
            return self._pop()
        except AttributeError:
            raise IndexError("pop from an empty Heap")

    def pop_safe(self):
        """Like pop, but returns None when the heap is empty."""
        return self._root and self._pop()

    def push(self, x):
        """Push element x onto the heap."""
        self._root = _meld(self._root, _Node(x, []))
        self._nelems += 1

    @property
    def top(self):
        """The smallest element of the heap."""
        try:
            return self._root.key
        except AttributeError:
            raise IndexError("min of an empty Heap")


_Node = namedtuple("_Node", "key sub")


def _meld(l, r):
    """Meld (merge) two pairing heaps, destructively."""
    # We deviate from the usual (persistent) treatment of pairing heaps by
    # using list's destructive, amortized O(1) append rather than a "cons".
    if l is None:
        return r
    elif r is None:
        return l
    elif l.key < r.key:
        l.sub.append(r)
        return l
    else:
        r.sub.append(l)
        return r


def _pair(heaps):
    """Pair up (recursively meld) a list of heaps."""
    return reduce(_meld, heaps, None)

