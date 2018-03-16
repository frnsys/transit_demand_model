freqs_a = [{'period': 3600, 'end': 17999, 'start': 14400}, {'period': 1200, 'end': 28799, 'start': 18000}, {'period': 3600, 'end': 32399, 'start': 28800}, {'period': 1800, 'end': 43199, 'start': 32400}, {'period': 3600, 'end': 46799, 'start': 43200}, {'period': 3600, 'end': 57599, 'start': 50400}, {'period': 1800, 'end': 64799, 'start': 57600}, {'period': 3600, 'end': 79199, 'start': 64800}, {'period': 1800, 'end': 82799, 'start': 79200}, {'period': 3600, 'end': 86399, 'start': 82800}]
freqs_b = [{'period': 3600, 'end': 3599, 'start': 0}, {'period': 1800, 'end': 43199, 'start': 21600}]

"""
note: start is the first departure from the stop, end is the last departure (I think? need to check)
can A transfer to B? (where A is a stop on a trip X and B is a stop on a trip Y. B and A may be the same physical stop)
1) if B ENDS before A STARTS, then NO. (No matter what X vehicle you arrive on at A, there will be no more Y vehicles departing from B)
2) if B ENDS before A ENDS, then SOMETIMES.
    - If 1) holds, then there are some X vehicles at A where you can transfer to Y vehicles at B, but once the Y service ends at B, there will still be X vehicles arriving at A that can no longer make that transfer
3) if B ENDS after A STARTS, then SOMETIMES
    - SOMETIMES if 7) holds
    - CONTRADICTORY with 1)
4) if B ENDS after A ENDS, then SOMETIMES. See 2
5) if B STARTS after A ENDS, then ALWAYS. (You can arrive on any X vehicle at A and wait until the Y service starts from B)
6) if B STARTS before A ENDS, then SOMETIMES
7) if B STARTS after A STARTS, then SOMETIMES

to put it another way, as long as a span in B ends after some span in A begins, there will be SOME transfer possible.

Working out 1):

if ALL spans' ENDs in B < ANY spans' STARTs in A -> False
otherwise -> True

or, to put it another way:

at least one span in B must END after at least one span in A
"""

"""
for a stop A and a trip X that stops at A,
we have an ARRIVAL schedule, which is the frequency at which trip X vehicles arrive at A.
we also have a DEPARTURE schedule, which is the frequency at which trip X vehicles depart from A.

we are assuming that these schedules are the same, i.e. that vehicles depart very soon after they arrive.

though, we could encode the gap between ARRIVAL and DEPARTURE schedule as just an integer offset, e.g. -2
to indicate that the DEPARTURE is at START, and the vehicle arrives at START-2.
"""
