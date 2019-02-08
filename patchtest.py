import diff_match_patch as dmp_module
from termcolor import colored

text1 = """
I am the very model of a modern Major-General,
I've information vegetable, animal, and mineral,
I know the kings of England, and I quote the fights historical,
From Marathon to Waterloo, in order categorical.
"""

text2 = """
I am the very model of a modern Major-General,
I've had information vegetable and mineral,
I know the kings of England, and I quote the fights historical,
From Marathon to Waterloo, in order categorical.
"""

text3 = """
I am the very model of a modern Major-General,
I've information vegetable, and mineral,
You know queens of England, and I quote the fights historical,
From Marathon to Waterloo, in order categorical.
"""

dmp = dmp_module.diff_match_patch()
print("DIFF 1 and 2")
patches_2 = dmp.patch_make(text1, text2)
for patch in patches_2:
    print(patch)

print("DIFF 1 and 3")
patches_3 = dmp.patch_make(text1, text3)
for patch in patches_3:
    print(patch)

print("Applying delta 2")
new_text, results = dmp.patch_apply(patches_2, text1)
print(results)

print("Computed text:")
print(new_text)

print("Applying delta 3")
new_text, results = dmp.patch_apply(patches_3, new_text)
print(results)

print("Final text:")
print(new_text)

print("============================")

print("Applying delta 3")
new_text_2, results = dmp.patch_apply(patches_3, text1)
print(results)

print("Computed text:")
print(new_text_2)

print("Applying delta 2")
new_text_2, results = dmp.patch_apply(patches_2, new_text_2)
print(results)

print("Final text:")
print(new_text_2)

print("Equal?", new_text == new_text_2)

print('=============MERGE==============')


diffs = three_way_merge(text1, text2, text3)
print_diff(diffs)

#diffs = dmp.diff_main(text1, text2)
#dmp.diff_cleanupSemantic(diffs)

patches = dmp.patch_make(text1, diffs)
patches_text = dmp.patch_toText(patches)
patches_new = dmp.patch_fromText(patches_text)
text2_new, results = dmp.patch_apply(patches_new, text1)
assert results == [True for result in results]
assert len(results) == len(patches)
print(text2_new)

