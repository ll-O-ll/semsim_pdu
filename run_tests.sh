#!/bin/bash
# Run PDU ICD Integration Test

echo "======================================================================"
echo "PDU ICD Integration Test"
echo "======================================================================"
echo ""
echo "This test will:"
echo "  1. Start SEMSIM server in simulator mode"
echo "  2. Send OBC commands via TCP/IP"
echo "  3. Verify ICD-compliant responses"
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
