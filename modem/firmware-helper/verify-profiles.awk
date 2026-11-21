# Stock raw keys must remain simultaneously discoverable on separate ports.
NR == 1 {
    header = (NF == 5 && $1 == "Service" && $2 == "Version" &&
              $3 == "Instance" && $4 == "Node" && $5 == "Port")
    next
}
NF {
    count++
    if (count > 10 || NF < 5 || ("x" $1) != "x4096" ||
        $2 !~ /^([1-9]|10)$/ || ("x" $3) != "x0" ||
        ("x" $4) != ("x" expected_node) || $5 !~ /^[1-9][0-9]*$/ ||
        length($5) > 10 || $5 >= 4294967294) {
        bad = 1
        next
    }
    if (versions[$2]++ || ports[$5]++)
        bad = 1
}
END {
    if (!header || bad || count != 10 ||
        expected_node !~ /^(0|[1-9][0-9]*)$/ || length(expected_node) > 10 ||
        expected_node >= 4294967295)
        exit 1
    for (key = 1; key <= 10; key++)
        if (versions[key] != 1)
            exit 1
}
