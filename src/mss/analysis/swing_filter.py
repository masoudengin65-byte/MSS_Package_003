"""
MSS Swing Filter

Removes duplicated consecutive swings.

Input:
    HIGH HIGH LOW LOW HIGH ...

Output:
    HIGH LOW HIGH ...
"""

from mss.analysis.swing_detector import Swing


class SwingFilter:

    def filter(self, swings):

        if not swings:
            return []

        result = [swings[0]]

        for current in swings[1:]:

            last = result[-1]

            # دو Swing از یک نوع
            if current.kind == last.kind:

                if current.kind == "HIGH":

                    # High بزرگتر را نگه دار
                    if current.price > last.price:
                        result[-1] = current

                else:

                    # Low کوچکتر را نگه دار
                    if current.price < last.price:
                        result[-1] = current

            else:

                result.append(current)

        return result