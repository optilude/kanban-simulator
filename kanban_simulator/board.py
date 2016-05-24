import abc
import itertools
import copy
import collections

#
# Interfaces
#

class CardSource(object):
    """Yields cards, either from a backlog, a previous column,
    or the splitting of a parent card.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def next_card(self, card_type=None):
        """Get the next available card of the desired card_type (or any card,
        if not set), removing it from the source, or None if there
        are no more cards.

        Card types are class objects extending Card.
        """

class CardContainer(object):
    """A place (like a column, backlog or lane) where cards are held
    """

    __metaclass__ = abc.ABCMeta

    name = ""
    cards = []

    @abc.abstractproperty
    def is_empty(self):
        """Return True if the container is empty
        """

class TimeAware(object):
    """Acts when time passes
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def tick(self, date):
        """Record that one day has passed
        """

class LocationAware(object):
    """Acts when location (backlog, column, donelog) changes
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def pull_to(self, location):
        """Record that the location has changed
        """


class PullCapable(object):
    """Acts when it's time to attempt to pull
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def pull(self):
        """Attempt to pull a card from the card source
        """

#
# Helpers
#


class QueueCardSource(CardContainer, CardSource):
    """Card source for things that act like queues
    """

    def __init__(self, name, cards=None):
        self.name = name
        self.cards = [] if cards is None else cards

    def next_card(self, card_type=None):
        if len(self.cards) > 0:
            if card_type is None:
                return self.cards.pop(0)
            else:
                card = next((c for c in self.cards if isinstance(c, card_type)), None)
                if card is not None:
                    self.cards.remove(card)
                    return card

        return None

    @property
    def is_empty(self):
        return len(self.cards) == 0

class ChainingQueueCardSource(QueueCardSource):
    """Card source for queues with immediate upstream columns
    """

    def __init__(self, name, cards=None, card_source=None):
        super(ChainingQueueCardSource, self).__init__(name, cards)
        self.card_source = card_source

    def next_card(self, card_type=None):
        card = super(ChainingQueueCardSource, self).next_card(card_type)
        if card is None and self.card_source is not None:
            card = self.card_source.next_card(card_type)
        return card

class AggregateCardSource(CardSource):
    """A card source that returns cards from multiple other card sources
    """

    def __init__(self, card_sources):
        self.card_sources = card_sources

    def next_card(self, card_type=None):
        for source in self.card_sources:
            card = source.next_card(card_type)
            if card is not None:
                return card
        return None

#
# Board structure
#

class Board(TimeAware, PullCapable, CardContainer):
    """A Kanban board, with one or more lanes, a backlog and a donelog.
    """

    def __init__(self, name, lanes, backlog):
        self.name = name
        self.lanes = lanes
        self.backlog = backlog
        self.donelog = Donelog()

        self.wire()

    def clone(self):
        return copy.deepcopy(self)

    # Simulation

    def run_simulation(self, max_days=100000):
        """Run a simulation once and return a (day, board) tuple.

        The history of each card can be obtained from the `board.donelog.cards`
        list on this instance.

        `max_days` is a guard to stop infinite loops.

        This will mutate the board's state. Use `clone` as required to keep
        the initial state.
        """

        day = 0
        for day, board in self:
            if day > max_days:
                raise OverflowError
        return day, self

    def run_monte_carlo_simulation(self, trials=100, max_days=100000):
        """Run the simulation `trials` times, each up to `max_days` days.

        Returns a list of `(day, board)` tuples, soted by day.
        """

        finishes = []

        for attempt in range(trials):
            day, board = self.clone().run_simulation(max_days=max_days)
            finishes.append((day, board,))

        return sorted(finishes, key=lambda x: x[0])

    def __iter__(self):
        """Loop through the simulation, yielding a (day, board,) tuple each
        day until the board is empty (everything is in the Done log).
        """
        day = 0

        while not self.is_empty:
            day += 1

            self.pull()
            self.tick(day)

            yield (day, self,)

    def wire(self, force=False):
        """Wire up lanes with the backlog unless one is already set,
        and wire an aggregate card source of all the lanes to the
        master donelog.
        """
        for lane in self.lanes:

            if lane.backlog is None or force:
                lane.backlog = self.backlog

            lane.wire(force)

        self.donelog.card_source = AggregateCardSource([l.donelog for l in self.lanes])

    def tick(self, date):
        for lane in self.lanes:
            lane.tick(date)

    def pull(self):
        self.donelog.pull()
        for lane in self.lanes:
            lane.pull()

    @property
    def cards(self):
        return itertools.chain(self.backlog.cards, *(l.cards for l in self.lanes))

    @property
    def is_empty(self):
        return self.backlog.is_empty and all((l.is_empty for l in self.lanes))

    def to_html(self):
        return """
        <table class='kanban-board'>
            <thead>
                <tr>
                    <th>Backlog</th>
                    <th></th>
                    <th>Done</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class='backlog'>%(backlog)s</td>
                    <td class='lanes'>%(lanes)s</td>
                    <td class='done'>%(done)s</td>
                </tr>
            </tbody>
        </table>
        """ % {
            'backlog': self.backlog.to_html(),
            'lanes': '<br />\n'.join((l.to_html() for l in self.lanes)),
            'done': self.donelog.to_html(),
        }

class Backlog(ChainingQueueCardSource):
    """A FIFO backlog
    """

    def __init__(self, name="Backlog", cards=None, card_source=None):
        super(Backlog, self).__init__(name, cards, card_source)

    def __repr__(self):
        return "<Backlog %s>" % self.name

    def to_html(self):
        return '\n'.join((c.to_html() for c in self.cards))


class Donelog(ChainingQueueCardSource, PullCapable):
    """The opposite of a backlog - the cards that are done.

    The card_source usually doesn't need to be set, as it is set
    when the Board is wired.
    """

    def __init__(self, name="Done", cards=None, card_source=None):
        ChainingQueueCardSource.__init__(self, name, cards, card_source)

        self.name = name
        self.cards = [] if cards is None else cards

    def __repr__(self):
        return "<Donelog %s>" % self.name

    def pull(self):
        # Greedily pull cards
        while True:
            card = self.card_source.next_card()

            if card is None:
                break

            self.cards.append(card)
            card.pull_to(self)

    def to_html(self):
        return '\n'.join((c.to_html() for c in self.cards))

class Lane(TimeAware, CardContainer, PullCapable):
    """A lane containing multiple columns.

    The backlog is normally wired in from the parent Board,
    and the donelog will be created automatically if not passed in.
    """

    def __init__(self, name, columns, backlog=None, wip_limit=None):
        self.name = name
        self.columns = columns

        self.backlog = backlog
        self.donelog = Donelog(name=self.name + " Done")

        self.wip_limit = wip_limit

    def clone(self, name=None, backlog=None):
        lane = copy.copy(self)

        lane.columns = [c.clone() for c in self.columns]
        lane.backlog = backlog if backlog is not None else self.backlog
        lane.donelog = Donelog(name=self.name + " Done")

        if name is not None:
            lane.name = name

        lane.wire(force=True)

        return lane

    def wire(self, force=False):
        source = self.backlog

        for column in self.columns:
            column.lane = self
            if column.card_source is None or force:
                column.card_source = source
            source = column

        self.donelog.card_source = source

    def tick(self, date):
        for column in self.columns:
            column.tick(date)

    def pull(self):
        self.donelog.pull()

        columns = self.columns
        if self.wip_limit is not None:
            total = sum((len(list(c.cards)) for c in self.columns))
            if total >= self.wip_limit:
                # don't start new work in the lane if we are over the WIP limit
                columns = columns[1:]

        for c in reversed(columns):
            c.pull()

    @property
    def cards(self):
        return itertools.chain(self.backlog.cards, *(c.cards for c in self.columns))

    @property
    def is_empty(self):
        return self.backlog.is_empty and all((c.is_empty for c in self.columns))

    def __repr__(self):
        return "<Lane %s>" % self.name

    def to_html(self, show_backlog=False):

        extra_header = ""
        extra_body = ""
        if show_backlog:
            extra_header = "<th>%s</th>" % self.backlog.name
            extra_body = "<td>%s</td>" % '\n'.join((c.to_html() for c in self.backlog.cards))

        def column_header(col):
            wip_limit = getattr(col, 'wip_limit', None)
            if wip_limit:
                return "%s (%d)" % (col.name, wip_limit,)
            return col.name

        return """
        <div class='lane-name'>%(name)s</div>
        <table class='lane'>
            <thead>
                <tr>%(headers)s</tr>
            </thead>
            <tbody>
                <tr>%(columns)s</tr>
            </tbody>
        </table>
        """ % {
            'name': self.name,
            'headers': extra_header + "\n".join(("<th>%s</th>" % column_header(c) for c in self.columns)),
            'columns': extra_body + "\n".join(("<td>%s</td>" % c.to_html() for c in self.columns)),
        }

class Column(TimeAware, PullCapable, CardContainer, CardSource):
    """A column in a lane

    name:        name of the column
    touch:       either a number of days or a callable returning such,
                 indicating how long an item is worked on in this column
                 ("touch time")
    wip_limit:   max number of cards allowed at any one time
    card_type:   the Card type (class) accepted, or None if all types accepted
    card_source: the CardSource where this column pulls from

    It is normally not necerssary to set card_source, because it is set when
    the Board is wired up in the constructor.
    """

    def __init__(self, name, touch, wip_limit=None, card_type=None, card_source=None):
        self.name = name
        self.touch = touch
        self.wip_limit = wip_limit
        self.card_type = card_type
        self.card_source = card_source
        self.lane = None

        self.cards = []

    def clone(self, name=None):
        column = copy.copy(self)
        column.cards = []

        if name is not None:
            column.name = name

        return column

    def tick(self, date):
        for card in self.cards:
            card.tick(date)

    def pull(self):
        while True:
            if self.wip_limit is not None and len(self.cards) >= self.wip_limit:
                break

            card = self.card_source.next_card(self.card_type)
            if card is None:
                break

            self.cards.append(card)
            card.pull_to(self)

            # crystal ball time...
            card.record_touch(self, self.touch() if callable(self.touch) else self.touch)

    def next_card(self, card_type=None):
        if len(self.cards) == 0:
            return None

        card = next((c for c in self.cards if card_type is None or isinstance(c, card_type)), None)
        if card is None:
            return None

        card_history = card.history.get(self, card._new_record())

        # Are we done working on it?
        if card_history['age'] < card_history['touch']:
            return None

        self.cards.remove(card)
        return card

    @property
    def is_empty(self):
        return len(self.cards) == 0

    def __repr__(self):
        return "<Column %s of %s>" % (self.name, self.lane.name if self.lane is not None else "<no lane>")

    def to_html(self):
        return '\n'.join((c.to_html() for c in self.cards))


class QueueColumn(Column):
    """A queue column in a lane

    name:        name of the column
    wip_limit:   max number of cards allowed at any one time
    card_type:   the Card type (class) accepted, or None if all types accepted
    card_source: the CardSource where this column pulls from

    It is normally not necerssary to set card_source, because it is set when
    the Board is wired up in the constructor.
    """

    def __init__(self, name, wip_limit=None, card_type=None, card_source=None):
        super(QueueColumn, self).__init__(name, touch=0, wip_limit=wip_limit, card_type=card_type, card_source=card_source)

    def next_card(self, card_type=None):
        card = super(QueueColumn, self).next_card(card_type)
        if card is None and self.card_source is not None:
            card = self.card_source.next_card(card_type)
        return card

    def __repr__(self):
        return "<QueueColumn %s of %s>" % (self.name, self.lane.name if self.lane is not None else "<no lane>")

class SublaneColumn(Column):
    """A column in a lane with one or more sub-lanes

    name:          name of the column
    lane_template: a Lane to describe each sub-lane
    wip_limit:     WIP limit, aka number of lanes
    card_type:     the Card type (class) accepted, or None if all types accepted
    card_source:   the CardSource where this column pulls from

    It is normally not necerssary to set card_source, because it is set when
    the Board is wired up in the constructor.

    When a card is pulled, it must be a CardSource (e.g. an Epic). It will be set
    as the lane backlog. Only when this card source is exhausted will the card be
    allowed to be pulled into the next column in the parent lane.
    """

    def __init__(self, name, lane_template, wip_limit, card_type=CardSource, card_source=None):
        self.name = name
        self.touch = 0
        self.wip_limit = wip_limit
        self.card_type = card_type
        self.card_source = card_source

        self.lane_template = lane_template
        self.lanes = []

    def clone(self):
        column = copy.copy(self)

        column.lane_template = self.lane_template.clone()
        column.lanes = []

        return column

    @property
    def cards(self):
        return (l.backlog for l in self.lanes)

    @property
    def is_empty(self):
        return len(self.lanes) == 0 or all((l.is_empty for l in self.lanes))

    def tick(self, date):
        for lane in self.lanes:
            lane.backlog.tick(date)  # tick the epic card
            lane.tick(date)  # tick everything in the lane

    def pull(self):
        for lane in self.lanes:
            lane.pull()

        while True:
            if self.wip_limit is not None and len(self.lanes) >= self.wip_limit:
                break

            card = self.card_source.next_card(self.card_type)
            if card is None:
                break

            # Create a new lane for the card and pull
            lane = self.lane_template.clone()
            lane.backlog = card
            lane.wire()
            lane.pull()

            self.lanes.append(lane)
            card.pull_to(self)

    def next_card(self, card_type=None):
        target_lane = None

        for lane in self.lanes:
            if (card_type is None or isinstance(lane.backlog, card_type)) and lane.is_empty:
                target_lane = lane
                break

        if target_lane is not None:
            self.lanes.remove(target_lane)
            return target_lane.backlog

        return None

    def __repr__(self):
        return "<SublaneColumn %s of %s>" % (self.name, self.lane.name if self.lane is not None else "<no lane>")

    def to_html(self):
        return "<br />\n".join((l.to_html(show_backlog=True) for l in self.lanes))

#
# Cards
#

class Card(TimeAware, LocationAware):
    """A card, e.g. an epic or a story.
    """

    def __init__(self, name, data=None):
        self.name = name
        self.data = data

        self.age = 0
        self.touch = 0
        self.dates = []

        self.location = None  # current CardContainer
        self.history = collections.OrderedDict()  # column -> {'touch': <work duration>, 'age': <total time in column>, 'dates': <list of dates>}

    def _new_record(self):
        return {'touch': 0, 'age': 0, 'dates': []}

    def record_touch(self, location, touch):
        self.touch += touch

        record = self.history.setdefault(location, self._new_record())
        record['touch'] = touch

    def tick(self, date):
        self.age += 1
        self.dates.append(date)

        record = self.history.setdefault(self.location, self._new_record())
        record['age'] += 1
        record['dates'].append(date)

    def pull_to(self, location):
        self.history.setdefault(location, self._new_record())
        self.location = location

    def __repr__(self):
        return "<Card %s>" % self.name

    def to_html(self):
        return "<div class='card'>%s[%d,%d]</div>" % (
            self.name,
            self.history.get(self.location, {}).get('age', 0),
            self.age,
        )

class Epic(Card, QueueCardSource):
    """An epic, which may be split into stories later.

    The splits dict contains column names as keys and a
    number representing the number of stories to split into
    as the epic enters the desired column.
    """

    def __init__(self, name, data=None, splits={}):
        QueueCardSource.__init__(self, name=name, cards=[])
        Card.__init__(self, name, data)

        self.splits = splits

    def pull_to(self, location):
        super(Epic, self).pull_to(location)

        if location is not None and location.name in self.splits:
            self.cards.extend([
                Story("%s-%02d" % (self.name, i + 1,), parent_epic=self)
                for i in range(self.splits[location.name])
            ])

    def __repr__(self):
        return "<Epic %s>" % self.name

class Story(Card):
    """A story, possibly with a parent epic.
    """

    def __init__(self, name, data=None, parent_epic=None):
        super(Story, self).__init__(name, data)
        self.parent_epic = parent_epic

    def __repr__(self):
        return "<Story %s>" % self.name
