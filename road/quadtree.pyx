"""
adapted from:
https://github.com/karimbahgat/Pyqtree/blob/master/pyqtree.py

TODO implement remove methods
"""

from libcpp.vector cimport vector

ctypedef struct Rect:
    double x1
    double y1
    double x2
    double y2

ctypedef struct QuadNode:
    unsigned int id
    Rect rect



cdef Rect normalize_rect(double x1, double y1, double x2, double y2):
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    return Rect(x1=x1, y1=y1, x2=x2, y2=y2)


cdef class QuadTree:
    cdef:
        unsigned int max_items
        unsigned int max_depth
        double x, y
        double width, height
        unsigned int depth
        vector[QuadNode] nodes
        list children

    @classmethod
    def from_bbox(cls, tuple bbox, unsigned int max_items=10, unsigned int max_depth=20):
        x1, y1, x2, y2 = bbox
        width, height = abs(x2-x1), abs(y2-y1)
        midx, midy = x1+width/2.0, y1+height/2.0
        depth = 0
        return cls(midx, midy, width, height, depth, max_items, max_depth)

    def __init__(self, double x, double y, double width, double height, unsigned int depth, unsigned int max_items=10, unsigned int max_depth=20):
        self.x = x
        self.y = y
        self.depth = depth
        self.width = width
        self.height = height
        self.children = []
        self.max_items = max_items
        self.max_depth = max_depth

    def insert(self, unsigned int id, tuple bbox):
        cdef Rect rect = normalize_rect(bbox[0], bbox[1], bbox[2], bbox[3])
        self.__insert(id, rect)

    def _insert(self, unsigned int id, Rect rect):
        return self.__insert(id, rect)

    cdef __insert(self, unsigned int id, Rect rect):
        cdef:
            QuadNode node

        rect = normalize_rect(rect.x1, rect.y1, rect.x2, rect.y2)

        if not self.children:
            node = QuadNode(id, rect)
            self.nodes.push_back(node)

            if self.nodes.size() > self.max_items and self.depth < self.max_depth:
                self._split()
        else:
            self._insert_into_children(id, rect)

    cdef _insert_into_children(self, unsigned int id, Rect rect):
        cdef:
            QuadNode node

        # if rect spans center then insert here
        if (rect.x1 <= self.x and rect.x2 >= self.x and
            rect.y1 <= self.y and rect.y2 >= self.y):
            node = QuadNode(id, rect)
            self.nodes.push_back(node)
        else:
            # try to insert into children
            if rect.x1 <= self.x:
                if rect.y1 <= self.y:
                    self.children[0]._insert(id, rect)
                if rect.y2 >= self.y:
                    self.children[1]._insert(id, rect)
            if rect.x2 > self.x:
                if rect.y1 <= self.y:
                    self.children[2]._insert(id, rect)
                if rect.y2 >= self.y:
                    self.children[3]._insert(id, rect)

    cdef _split(self):
        cdef:
            double quartwidth = self.width / 4.0
            double quartheight = self.height / 4.0
            double halfwidth = self.width / 2.0
            double halfheight = self.height / 2.0
            double x1 = self.x - quartwidth
            double x2 = self.x + quartwidth
            double y1 = self.y - quartheight
            double y2 = self.y + quartheight
            unsigned int new_depth = self.depth + 1
            QuadTree q1 = QuadTree(x=x1, y=y1, width=halfwidth, height=halfheight, depth=new_depth, max_items=self.max_items, max_depth=self.max_depth)
            QuadTree q2 = QuadTree(x=x1, y=y2, width=halfwidth, height=halfheight, depth=new_depth, max_items=self.max_items, max_depth=self.max_depth)
            QuadTree q3 = QuadTree(x=x2, y=y1, width=halfwidth, height=halfheight, depth=new_depth, max_items=self.max_items, max_depth=self.max_depth)
            QuadTree q4 = QuadTree(x=x2, y=y2, width=halfwidth, height=halfheight, depth=new_depth, max_items=self.max_items, max_depth=self.max_depth)
            vector[QuadNode] nodes

        self.children = [q1, q2, q3, q4]

        nodes.swap(self.nodes)
        for node in nodes:
            self._insert_into_children(node.id, node.rect)

    cpdef intersect(self, tuple bbox):
        cdef:
            set results = set()
            Rect rect = normalize_rect(bbox[0], bbox[1], bbox[2], bbox[3])
        return self._intersect(rect, results)

    cpdef _intersect(self, Rect rect, set results):
        return self.__intersect(rect, results)

    cdef __intersect(self, Rect rect, set results):
        # search children
        if self.children:
            if rect.x1 <= self.x:
                if rect.y1 <= self.y:
                    self.children[0]._intersect(rect, results)
                if rect.y2 >= self.y:
                    self.children[1]._intersect(rect, results)
            if rect.x2 >= self.x:
                if rect.y1 <= self.y:
                    self.children[2]._intersect(rect, results)
                if rect.y2 >= self.y:
                    self.children[3]._intersect(rect, results)

        # search node at this level
        for node in self.nodes:
            if (node.rect.x2 >= rect.x1 and node.rect.x1 <= rect.x2 and
                node.rect.y2 >= rect.y1 and node.rect.y1 <= rect.y2):
                results.add(node.id)
        return results
