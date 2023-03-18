rm -rf state_ls0 state_ls1 state_ls2
mkdir state_ls0
mkdir state_ls1
mkdir state_ls2
python -m lstream.controller --index 0 --state-dir state_ls0 > 0.log 2>&1 &
PID0=$!
python -m lstream.controller --index 1 --state-dir state_ls1 > 1.log 2>&1 &
PID1=$!
python -m lstream.controller --index 2 --state-dir state_ls2 > 2.log 2>&1 &
PID2=$!

trap_ctrlc() {
    kill $PID0
    echo -e "\nkill=$? (0 = success)\n"
    wait $PID0
    kill $PID1
    echo -e "\nkill=$? (0 = success)\n"
    wait $PID1
    kill $PID2
    echo -e "\nkill=$? (0 = success)\n"
    wait $PID2
    rm -r state_ls0 state_ls1 state_ls2
    rm *.log

}

trap trap_ctrlc INT

# wait for all background processes to terminate
wait