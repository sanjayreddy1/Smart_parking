<!DOCTYPE html>
<html>
<head>
    <title>Print Bill - Smart Car Parking</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .print-container {
            width: 380px;
            margin: 30px auto;
            padding: 20px;
            border: 2px dashed #333;
            text-align: center;
        }
        .qr-code {
            margin-top: 15px;
        }
    </style>
</head>
<body onload="window.print()">
<div class="print-container">
    <h3>Smart Car Parking - Bill</h3>
    <hr>
    <p><strong>Slot ID:</strong> {{ bill.slot_id }}</p>
    <p><strong>Vehicle:</strong> {{ bill.vehicle_number }}</p>
    <p><strong>In-Time:</strong> {{ bill.in_time }}</p>
    <p><strong>Out-Time:</strong> {{ bill.out_time }}</p>
    <p><strong>Duration:</strong> {{ bill.duration_hours }} hrs</p>
    <p><strong>Date:</strong> {{ bill.date }}</p>
    <p><strong>Total:</strong> ₹{{ bill.amount }}</p>
    <div class="qr-code">
        <img src="data:image/png;base64,{{ qr_code }}" alt="QR Code">
    </div>
</div>
</body>
</html>
