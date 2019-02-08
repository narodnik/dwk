import diff_match_patch as dmp_module
from termcolor import colored

dmp = dmp_module.diff_match_patch()

def changes_table(text, diffs):
    changes = list(text)
    index = 0
    for change, change_text in diffs:
        if change == 1:
            continue
        for i, letter in enumerate(change_text):
            changes[index + i] = [change, letter, []]
        index += len(change_text)
    assert index == len(text)
    return changes

def merge_changes_tables(changes_2, changes_3):
    changes_merged = changes_2[:]
    for i, (change, letter, _) in enumerate(changes_3):
        if change == -1:
            changes_merged[i] = (-1, letter, [])
    return changes_merged

def append_additions(changes, diffs):
    index = 0
    for change, change_text in diffs:
        if change != 1:
            index += len(change_text)
            continue
        changes[index][2].append(change_text)

def emerge_diff_from_changes(changes):
    diff_merged = []
    previous_change = None
    previous_sentence = None
    for change, letter, add_list in changes:
        if add_list:
            # Add current stuff
            # ... only when not at the very start
            if previous_change is not None:
                assert previous_sentence is not None
                diff_merged.append((previous_change, previous_sentence))
            # Then additions
            additions = "".join(addition for addition in add_list)
            diff_merged.append((1, additions))
            # Reset
            previous_sentence = None
            previous_change = None

        # Continue along
        if change == previous_change:
            previous_sentence += letter
            continue

        # Push current sentence
        if previous_change is not None:
            diff_merged.append((previous_change, previous_sentence))
        # Reset
        previous_sentence = letter
        previous_change = change

    # Add remaining stuff
    diff_merged.append((previous_change, previous_sentence))
    return diff_merged

def print_diff(diffs):
    for change, diff in diffs:
        if change == 0:
            text = diff
        elif change == -1:
            text = colored(diff, 'red')
        elif change == 1:
            text = colored(diff, 'green')
        print(text, end='')

def three_way_merge(base_text_1, text_2, text_3):
    diffs_2 = dmp.diff_main(base_text_1, text_2)
    diffs_3 = dmp.diff_main(base_text_1, text_3)
    dmp.diff_cleanupSemantic(diffs_2)
    dmp.diff_cleanupSemantic(diffs_3)

    changes_2 = changes_table(base_text_1, diffs_2)
    changes_3 = changes_table(base_text_1, diffs_3)

    changes_merged = merge_changes_tables(changes_2, changes_3)
    # Add an extra empty to the change table at the end
    # for additions added to the end of the text
    changes_merged.append((0, '', []))

    append_additions(changes_merged, diffs_2)
    append_additions(changes_merged, diffs_3)

    return emerge_diff_from_changes(changes_merged)

def difference(base_text_1, text_2):
    diffs = dmp.diff_main(base_text_1, text_2)
    dmp.diff_cleanupSemantic(diffs)
    return diffs

if __name__ == '__main__':
    text_1 = """
I am the very model of a modern Major-General,
I've information vegetable, animal, and mineral,
I know the kings of England, and I quote the fights historical,
From Marathon to Waterloo, in order categorical.
"""

    text_2 = """
I am the very model of a modern Major-General,
I've had information vegetable and mineral,
I know the kings of England, and I quote the fights historical,
From Marathon to Waterloo, in order categorical.
"""

    text_3 = """
I am the very model of a modern Major-General,
I've information vegetable, and mineral,
You know queens of England, and I quote the fights historical,
From Marathon to Waterloo, in order categorical.
"""

    print('==== Diff(1, 2) ====')
    diffs = difference(text_1, text_2)
    print_diff(diffs)
    print('====================')
    print()

    print('==== Diff(1, 3) ====')
    diffs = difference(text_1, text_3)
    print_diff(diffs)
    print('====================')
    print()

    print('=== Diff(1, 2, 3) ==')
    diffs = three_way_merge(text_1, text_2, text_3)
    print_diff(diffs)
    print('====================')

