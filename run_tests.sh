#!/bin/bash
# Run PDU ICD Integration Test

echo "======================================================================"
echo "PDU ICD Integration Test"
echo "======================================================================"
echo ""
echo "PREREQUISITES:"
echo "  1. Start SEMSIM server in a separate terminal:"
echo "     python semsim.py --mode simulator --tcp-ip 127.0.0.1 --tcp-port 5004"
echo ""
echo "  2. Wait for server to be ready (you'll see 'TMTC Manager started')"
echo ""
echo "  3. Then run this test script"
echo ""
echo "======================================================================"
echo ""
echo "Starting test suite..."
echo "======================================================================"
echo ""

# Run ICD integration test
python -m unittest tests.test_icd_integration -v

echo ""
echo "======================================================================"
echo "Test completed!"
echo "======================================================================"
