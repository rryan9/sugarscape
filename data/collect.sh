#! /bin/bash

files=( altruist bentham default egoist modified topAltruist topBentham topEgoist topModified rankedAltruist rankedBentham rankedDefault rankedEgoist rankedModified )

# Create working configs to avoid clobbering permanent configs
for f in "${files[@]}"
do
    cp $f.config $f.json
done

n=10
for i in $( seq 1 $n )
do
    # Generate a random seed
    seed=$RANDOM
    sedstr="s/\(\"seed\"\:\s\).*,/\1$seed,/g"
    echo "Running simulation for random seed $seed ($i/$n)"

    for f in "${files[@]}"
    do
        # Apply seed to config file
        sed -i $sedstr ./$f.json
        # Run simulation for configs and rename resulting log
        python ../sugarscape.py --conf $f.json > $f$i.log
        python ../logparse.py --log log.json >> $f$i.log
        mv log.json $f$i.json
    done
done

# Clean up working configs
for f in "${files[@]}"
do
    rm $f.json
done

exit 0
