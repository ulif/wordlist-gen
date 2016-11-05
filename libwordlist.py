# -*- coding: utf-8 -*-
#  libwordlist -- tools for generating wordlists
#  Copyright (C) 2016  Uli Fouquet
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""libwordlist -- a library for wordlist-related operations.
"""
from __future__ import unicode_literals
import logging
import os
import random
import unicodedata

DICE_SIDES = 6  # we normally handle 6-sided dice.


#: A logger for use with diceware-list related messages.
logger = logging.getLogger("libwordlist")
logger.addHandler(logging.NullHandler())


def normalize(text):
    """Normalize text.
    """
    TRANSFORMS = {
        'ä': 'ae', 'Ä': 'AE', "æ": 'ae', "Æ": 'AE',
        'ö': 'oe', 'Ö': 'OE', "ø": 'oe', "Ø": 'OE',
        "ü": 'UE', "Ü": 'UE',
        'ß': 'ss'
    }
    transformed = "".join([TRANSFORMS.get(x, x) for x in text])
    nfkd_form = unicodedata.normalize("NFKD", transformed)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def base10_to_n(num, base):
    """Turn base-10 integer `num` into base-`base` form.

    Returns a list of numbers representing digits in `base`.

    For instance in base-2 we have only the digits ``0`` and
    ``1``. Turning the base-10 integer ``5`` into a base-2 number
    results in ``101`` or, as a list, in::

        >>> base10_to_n(5, base=2)
        [1, 0, 1]

    The result list represents the single "digits" of a differently
    based number. This holds also for 'digits' >= 10::

        >>> base10_to_n(127, base=16)
        [7, 15]

    which in hexadecimal notation would normally read ``0x7F``.
    """
    result = []
    curr = num
    while curr >= base:
        curr, digit = divmod(curr, base)
        result.append(digit)
    result.append(curr)
    result.reverse()
    return result


def filter_chars(iter, allowed=None):
    """Yield strings from `iter` that contain only chars from `allowed`.

    If `allowed` is `None`, no filtering is done at all.
    """
    if allowed is None:
        for elem in iter:
            yield elem
    else:
        logger.info("Filtering out chars.")
        logger.debug("  Allowed chars: %r" % allowed)
        line = 0
        for elem in iter:
            line += 1
            stripped = [x for x in elem if x in allowed]
            if len(stripped) >= len(elem):
                yield elem
            else:
                logger.debug("  Not allowed char in line %d" % line)


def idx_to_dicenums(
        item_index, dice_num, dice_sides=DICE_SIDES, separator='-'):
    """Get a set of dicenums for list item numbers.

    Turn an index number of a list item into a number of dice numbers
    representing this index. The dicenums are returned as a string like
    ``"1-2-2-6-2-5"``.

    `item_index` is the index number of some item.

    `dice_num` is the number of (n-sided) dice used.

    `dice_sides` is the number of sides per die.

    `separator` is the string to separate the result numbers.

    Example: we have two dice resulting in 36 possible combinations. If
    first possible combination is "1-1", second one "1-2" and so on,
    then we have a mapping from indexes 1..36 to dice combinations (from
    "1-1" up to "6-6").

    For a reasonable result, we expect

      0 <= `item_index` < `dice_num` ** `dice_sides`.

    Some examples::

        >>> idx_to_dicenums(0, 1)
        '1'
        >>> idx_to_dicenums(5, 1)
        '6'
        >>> idx_to_dicenums(0, 3)
        '1-1-1'
        >>> idx_to_dicenums(5, 3)
        '1-1-6'

    We are not restricted to (6-sided) dice. If we throw a (2-sided)
    coin 3 times, we have an index range from ``0`` to ``2^3 = 8``
    (there are 8 possible combinations of coin throws). Index ``5``
    then computes to::

        >>> idx_to_dicenums(5, 3, 2)
        '2-1-2'

    If `dice_sides` < 10, you can generate compressed output by leaving
    the separator out::

        >>> idx_to_dicenums(5, 3, 2, separator="")
        '212'

    """
    nums = [x+1 for x in base10_to_n(item_index, dice_sides)]
    padded = [1, ] * dice_num + nums
    return separator.join(["%s" % x for x in padded[-dice_num:]])


def shuffle_max_width_items(word_list, max_width=None):
    """Shuffle entries of `word_list` that have max width.

    Yields items in `word_list` in preserved order, but with maximum
    width entries shuffled. This helps to create lists, that have only
    entries with minimal width but a random set of maximum width
    entries.

    For instance::

      ["a", "b", "aa", "bb", "aaa", "bbb", "ccc"]

    could end up::

      ["a", "b", "aa", "bb", "ccc", "aaa", "bbb"]


    That means the three maximum-width elements at the end are returned
    in different order.
    """
    word_list = [x.strip() for x in word_list]
    if max_width is None:
        max_width = len(max(word_list, key=len))
    for entry in filter(lambda x: len(x) < max_width, word_list):
        yield entry
    max_width_entries = list(
        filter(lambda x: len(x) == max_width, word_list))
    random.shuffle(max_width_entries)
    for entry in max_width_entries:
        yield entry


def term_iterator(file_descriptors):
    """Yield terms from files in `file_descriptors`.

    Empty lines are ignored.

    `file_descriptors` must be open for reading.
    """
    for fd in file_descriptors:
        for term in fd:
            term = term.strip()
            if term:
                yield term


def base_terms_iterator(use_kit=True, use_416=True):
    """Iterator over all base terms.

    Base terms are those conained in the diceware416 and dicewarekit
    lists.

    With `use_kit` and `use_416` you can tell whether these files should
    be used for generating lists or not.

    Terms are delivered encoded. This way we make sure, they have the
    same binary format as oter terms read from files by `argparse`.
    """
    names = []
    if use_kit:
        logger.debug("Adding source list: dicewarekit.txt")
        names += ["dicewarekit.txt", ]
    if use_416:
        logger.debug("Adding source list: diceware416.txt")
        names += ["diceware416.txt"]
    dir_path = os.path.join(os.path.dirname(__file__))
    fd_list = [open(os.path.join(dir_path, name), "r") for name in names]
    for term in term_iterator(fd_list):
        yield term


def min_width_iter(iterator, num, shuffle_max_width=True):
    """Get an iterable with `num` elements and minimal 'list width' from
    items in `iterator`.

    If 'list width' is the sum of length of all items contained in a
    list or iterable, then `min_list_width` generates an iterator over
    `num` elements in this list/iterable, which results in a list with
    minimal 'list width'.

    For instance, for a list ['a', 'bb', 'ccc'] the list width would be
    1 + 2 + 3 = 6. For ['a', 'bbb'] this would be 1 + 3 = 4. If we want
    to build a minimum width version from the former list with two
    elements, these elements had to be 'a' and 'bb' (resulting in a list
    width of 3). All other combinations of two elements of the list
    would result in list widths > 3.

       >>> list(min_width_iter(["a", "ccc", "bb"], 2))
       ['a', 'bb']

    Please note that the iterator returned, delivers elements sorted by
    length first and terms of same length sorted alphabetically.

    """
    all_terms = sorted(iterator, key=lambda x: (len(x), x))
    if shuffle_max_width:
        max_width = len(all_terms[num - 1])
        all_terms = list(shuffle_max_width_items(all_terms, max_width))
    for term in all_terms[:num]:
        yield term


def is_prefix_code(iterator):
    """
        >>> is_prefix_code(["a", "b", "c", "d"])
        True

    """
    sorted_list = sorted([x for x in iterator])
    last_elem = None
    for elem in sorted_list:
        if last_elem and elem.startswith(last_elem):
            return False
        last_elem = elem
    return True
