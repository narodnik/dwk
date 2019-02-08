#!/bin/bash
mkdir -p foo/bar/
mkdir -p xyz

echo test123 > foo/bar/test123.txt
echo bar123 > foo/bar/bar123.txt
echo willdel > foo/bar/willdel.txt
echo willdel2 > foo/bar/willdel2.txt

echo footest > foo/footest.txt

echo abc > xyz/abc.txt
echo def > xyz/def.txt

rm -fr .darkwiki/
./darkwiki.py init

cd foo/
../darkwiki.py add bar/test123.txt
../darkwiki.py add bar/bar123.txt
cd ../
./darkwiki.py add foo/footest.txt
./darkwiki.py add xyz/abc.txt
./darkwiki.py add xyz/def.txt
./darkwiki.py add foo/bar/willdel.txt
./darkwiki.py add foo/bar/willdel2.txt

#./darkwiki.py read-index

./darkwiki.py commit

echo test123_dd > foo/bar/test123.txt
echo footest_dd > foo/footest.txt
echo newnew > newnew.txt

./darkwiki.py rm foo/bar/willdel.txt

./darkwiki.py add foo/bar/test123.txt
./darkwiki.py add foo/footest.txt
./darkwiki.py add newnew.txt
./darkwiki.py commit

echo test123_xx > foo/bar/test123.txt
echo abc_xx > xyz/abc.txt
echo anothernewnew > foo/anothernew.txt

./darkwiki.py add foo/bar/test123.txt
./darkwiki.py add xyz/abc.txt
./darkwiki.py add foo/anothernew.txt

cd xyz/
../darkwiki.py rm ../foo/bar/willdel2.txt
cd ../

echo abcabc > xyz/abc.txt
echo athernewnew > foo/anothernew.txt

echo
echo "Cached:"
./darkwiki.py diff --cached

echo
echo "Non-cached diff:"
./darkwiki.py diff

