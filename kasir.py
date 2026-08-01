import sqlite3
import io
import webbrowser
import os
import sys
from threading import Timer
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, send_file
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = 'supersecretkey_aditiya'
DB_NAME = 'kasir_percetakan.db'

def get_resource_path(filename):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

@app.route('/static/logo.png')
def serve_logo():
    logo_path = get_resource_path('logo.png')
    if os.path.exists(logo_path):
        return send_file(logo_path, mimetype='image/png')
    else:
        return "", 404

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_order TEXT,
        tanggal DATETIME DEFAULT CURRENT_TIMESTAMP,
        nama_pelanggan TEXT NOT NULL,
        nama_pesanan TEXT NOT NULL,
        qty INTEGER DEFAULT 1,
        omset INTEGER NOT NULL,
        modal INTEGER NOT NULL,
        laba INTEGER NOT NULL,
        pembulatan INTEGER DEFAULT 0,
        metode_bayar TEXT DEFAULT 'Cash',
        status_bayar TEXT DEFAULT 'LUNAS',
        jumlah_dp INTEGER DEFAULT 0,
        sisa_bayar INTEGER DEFAULT 0
    )''')
    
    cursor.execute("PRAGMA table_info(orders)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    new_columns = [
        ('kode_order', 'TEXT'),
        ('qty', 'INTEGER DEFAULT 1'),
        ('pembulatan', 'INTEGER DEFAULT 0'),
        ('status_bayar', "TEXT DEFAULT 'LUNAS'"),
        ('jumlah_dp', 'INTEGER DEFAULT 0'),
        ('sisa_bayar', 'INTEGER DEFAULT 0')
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATETIME DEFAULT CURRENT_TIMESTAMP,
        keterangan TEXT NOT NULL,
        jumlah INTEGER NOT NULL
    )''')
    
    conn.commit()
    conn.close()

def generate_kode_order():
    conn = get_db()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%y%m%d')
    cursor.execute("SELECT COUNT(*) FROM orders WHERE strftime('%Y-%m-%d', tanggal) = DATE('now', 'localtime')")
    count_today = cursor.fetchone()[0] + 1
    conn.close()
    return f"{today_str}{count_today:03d}"

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aditiya Grafika - Rekap Penjualan</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { margin: 0; padding: 0; background-color: #f4f6f9; display: flex; height: 100vh; overflow: hidden; }

        /* Sidebar Styling (AdminLTE Dark Theme) */
        .sidebar { width: 250px; background-color: #222d32; color: #b8c7ce; display: flex; flex-direction: column; flex-shrink: 0; }
        .sidebar-header { padding: 15px; text-align: center; background-color: #1a2226; border-bottom: 1px solid #10181e; }
        .sidebar-header img { max-width: 180px; max-height: 60px; height: auto; }
        
        .sidebar-menu { list-style: none; padding: 0; margin: 10px 0 0 0; }
        .sidebar-menu li a { display: flex; align-items: center; gap: 10px; padding: 12px 18px; color: #b8c7ce; text-decoration: none; font-size: 0.9rem; transition: 0.2s; }
        .sidebar-menu li a:hover, .sidebar-menu li.active a { background-color: #1e282c; color: #fff; border-left: 4px solid #3c8dbc; }
        .sidebar-heading { padding: 10px 18px; font-size: 0.7rem; text-transform: uppercase; color: #4b646f; background: #1a2226; font-weight: bold; }

        /* Main Content Layout */
        .main-content { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
        .top-navbar { background: #fff; padding: 15px 25px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d2d6de; }
        .top-navbar h1 { margin: 0; font-size: 1.4rem; color: #333; font-weight: 600; }
        .content-body { padding: 20px; flex: 1; }

        /* Dashboard Infoboxes (Cards) */
        .infobox-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .infobox { background: #fff; border-radius: 4px; padding: 15px; position: relative; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); color: white; }
        .infobox.blue { background: #00c0ef; }
        .infobox.red { background: #dd4b39; }
        .infobox.yellow { background: #f39c12; }
        .infobox.green { background: #00a65a; }
        .infobox .title { font-size: 0.75rem; text-transform: uppercase; font-weight: bold; opacity: 0.9; }
        .infobox .value { font-size: 1.5rem; font-weight: bold; margin-top: 5px; }

        /* Cards & Tables */
        .card { background: #fff; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-top: 3px solid #3c8dbc; padding: 20px; margin-bottom: 20px; }
        .card h2 { margin-top: 0; font-size: 1.1rem; color: #444; border-bottom: 1px solid #f4f4f4; padding-bottom: 10px; }

        .form-group { margin-bottom: 12px; }
        label { display: block; margin-bottom: 4px; font-weight: 600; font-size: 0.85rem; color: #555; }
        input, select { width: 100%; padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9rem; }
        
        .calculated-box { background: #eef9f1; border: 1px solid #c3e6cb; padding: 8px; border-radius: 4px; font-weight: bold; color: #155724; text-align: center; margin-top: 8px; font-size:0.9rem; }
        
        button, .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; background: #00a65a; color: white; border: none; padding: 8px 14px; font-size: 0.85rem; font-weight: bold; border-radius: 4px; cursor: pointer; text-decoration: none; }
        button:hover, .btn:hover { background: #008d4c; }

        .btn-excel { background: #107c41; }
        .btn-excel:hover { background: #0b5a2f; }
        .btn-pdf { background: #d9534f; }
        .btn-pdf:hover { background: #c9302c; }

        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.83rem; }
        th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #f4f4f4; }
        th { background-color: #f8f9fa; color: #555; font-weight: 600; }
        
        .action-btns { display: flex; gap: 4px; flex-wrap: wrap; }
        .btn-sm { padding: 4px 8px; font-size: 0.72rem; border-radius: 3px; border: none; cursor: pointer; color: white; text-decoration: none; }
        .btn-print-sm { background: #00c0ef; }
        .btn-wa-sm { background: #25D366; }
        .btn-edit-sm { background: #f39c12; }
        .btn-delete-sm { background: #dd4b39; }
        .btn-lunas-sm { background: #00a65a; }

        .badge-lunas { background: #00a65a; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.7rem; }
        .badge-dp { background: #f39c12; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.7rem; }

        /* Pop-Up Modal Styling */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 9999; }
        .modal-content { background: white; width: 480px; max-width: 90%; padding: 20px; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

        /* Struk Thermal Printable Style */
        @media print {
            @page { size: 58mm auto; margin: 0; }
            body * { visibility: hidden; }
            #struk-printable, #struk-printable * { visibility: visible; }
            #struk-printable { position: absolute; left: 0; top: 0; width: 58mm; padding: 2mm; font-family: 'Arial', sans-serif; font-size: 7.5pt; color: #000; box-sizing: border-box; }
            .no-print { display: none !important; }
        }
        .p-address { font-size: 6.5pt; text-align: center; margin: 2px 0 6px 0; line-height: 1.1; }
        .p-warning { font-size: 6.5pt; text-align: center; margin: 5px 0; font-style: italic; line-height: 1.1; }
        .p-line { border-top: 1px solid #000; margin: 4px 0; }
        .p-row { display: flex; justify-content: space-between; font-size: 7.5pt; margin: 1px 0; }
        .p-table { width: 100%; font-size: 7.5pt; border-collapse: collapse; margin: 4px 0; }
        .p-table th { text-align: left; border-bottom: 1px solid #000; padding-bottom: 2px; }
        .p-table td { padding: 2px 0; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
    </style>
</head>
<body>

<!-- Sidebar Navigasi Kiri -->
<div class="sidebar no-print">
    <div class="sidebar-header">
        <img src="/static/logo.png" alt="Aditiya Grafika" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
        <span style="display:none; color:white; font-weight:bold; font-size:1.1rem;">ADITIYA GRAFIKA</span>
    </div>

    <div class="sidebar-heading">MENU</div>
    <ul class="sidebar-menu">
        <li class="{{ 'active' if active_menu == 'dashboard' else '' }}">
            <a href="/?menu=dashboard">📊 Penjualan</a>
        </li>
        <li class="{{ 'active' if active_menu == 'pengeluaran' else '' }}">
            <a href="/?menu=pengeluaran">🛠 Pengeluaran</a>
        </li>
        <li>
            <a href="/backup">💾 Backup Database</a>
        </li>
    </ul>
</div>

<!-- Main Content Right -->
<div class="main-content no-print">
    <div class="top-navbar">
        <h1>Dashboard</h1>
        <div style="font-size:0.85rem; color:#777;">
            Tanggal: <b>{{ datetime_now_format }}</b>
        </div>
    </div>

    <div class="content-body">
        {% if active_menu == 'dashboard' %}
        <!-- HALAMAN DASHBOARD -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
            <form method="GET" action="/" style="display: flex; gap: 10px; align-items: center;">
                <input type="hidden" name="menu" value="dashboard">
                <label style="margin: 0; font-weight: bold;">Periode:</label>
                <input type="month" name="bulan" value="{{ bulan_pilihan }}" onchange="this.form.submit()" style="width: auto; padding: 6px 10px;">
            </form>
            <div style="display: flex; gap: 10px;">
                <button type="button" onclick="openTambahModal()" class="btn" style="background:#00a65a;">➕ Tambah Transaksi</button>
                <a href="/export/excel?bulan={{ bulan_pilihan }}" class="btn btn-excel">📊 Export Excel</a>
                <a href="/export/pdf?bulan={{ bulan_pilihan }}" class="btn btn-pdf">📄 Export PDF</a>
            </div>
        </div>

        <!-- Ringkasan 4 Card Infobox -->
        <div class="infobox-grid">
            <div class="infobox blue">
                <div class="title">Omset Kotor</div>
                <div class="value">Rp {{ "{:,.0f}".format(total_omset).replace(",", ".") }}</div>
            </div>
            <div class="infobox red">
                <div class="title">Modal Bahan</div>
                <div class="value">Rp {{ "{:,.0f}".format(total_modal).replace(",", ".") }}</div>
            </div>
            <div class="infobox yellow">
                <div class="title">Pengeluaran</div>
                <div class="value">Rp {{ "{:,.0f}".format(total_ops).replace(",", ".") }}</div>
            </div>
            <div class="infobox green">
                <div class="title">Laba Bersih</div>
                <div class="value">Rp {{ "{:,.0f}".format(laba_bersih_riil).replace(",", ".") }}</div>
            </div>
        </div>

        <!-- Tabel Laporan Penjualan -->
<!-- Tabel Laporan Penjualan (Dengan Kolom Qty) -->
        <div class="card" style="width: 100%; box-sizing: border-box;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f4f4f4; padding-bottom: 12px; margin-bottom: 15px;">
                <h2 style="margin: 0; border: none; padding: 0;">📜 Laporan Penjualan {{ nama_bulan_indo }}</h2>
                <input type="text" id="searchRekap" onkeyup="filterTable('searchRekap', 'tableRekap')" placeholder="🔍 Cari data..." style="width: 220px; padding: 6px 12px;">
            </div>
            
            <div style="overflow-x: auto; width: 100%;">
                <table id="tableRekap" style="width: 100%;">
                    <thead>
                        <tr>
                            <th>No. Order</th>
                            <th>Tgl</th>
                            <th>Pelanggan</th>
                            <th>Pesanan</th>
                            <th style="text-align: center;">Qty</th> <!-- DITAMBAHKAN KOLOM QTY -->
                            <th>Omset</th>
                            <th>Modal</th>
                            <th>Status</th>
                            <th>Aksi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for order in orders %}
                        <tr>
                            <td><small><b>{{ order['kode_order'] }}</b></small></td>
                            <td>{{ order['tanggal'][8:10] }}</td>
                            <td><b>{{ order['nama_pelanggan'] }}</b></td>
                            <td>{{ order['nama_pesanan'] }}</td>
                            <td style="text-align: center;"><b>{{ order['qty'] }}</b></td> <!-- ISI DATA QTY -->
                            <td>Rp {{ "{:,.0f}".format(order['omset']).replace(",", ".") }}</td>
                            <td style="color: #dd4b39;">Rp {{ "{:,.0f}".format(order['modal']).replace(",", ".") }}</td>
                            <td>
                                {% if order['status_bayar'] == 'LUNAS' %}
                                <span class="badge-lunas">LUNAS</span>
                                {% else %}
                                <span class="badge-dp">DP: {{ "{:,.0f}".format(order['jumlah_dp']).replace(",", ".") }}</span><br>
                                <small style="color:#dd4b39;">Sisa: {{ "{:,.0f}".format(order['sisa_bayar']).replace(",", ".") }}</small>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-btns">
                                    <button type="button" onclick="cetakStruk('{{ order['kode_order'] }}', '{{ order['nama_pelanggan'] }}', '{{ order['nama_pesanan'] }}', '{{ order['qty'] }}', '{{ order['omset'] }}', '{{ order['pembulatan'] }}', '{{ order['metode_bayar'] }}', '{{ order['tanggal'] }}', '{{ order['status_bayar'] }}', '{{ order['jumlah_dp'] }}', '{{ order['sisa_bayar'] }}')" class="btn-sm btn-print-sm">Struk</button>
                                    <button type="button" onclick="kirimWA('{{ order['nama_pelanggan'] }}', '{{ order['nama_pesanan'] }}', '{{ order['omset'] }}', '{{ order['status_bayar'] }}', '{{ order['sisa_bayar'] }}')" class="btn-sm btn-wa-sm">WA</button>
                                    {% if order['status_bayar'] == 'DP' %}
                                    <a href="/pelunasan/{{ order['id'] }}" onclick="return confirm('Tandai pesanan ini sudah LUNAS?')" class="btn-sm btn-lunas-sm">Pelunasan</a>
                                    {% endif %}
                                    <button type="button" onclick="openEditModal('{{ order['id'] }}', '{{ order['kode_order'] }}', '{{ order['nama_pelanggan'] }}', '{{ order['nama_pesanan'] }}', '{{ order['qty'] }}', '{{ order['omset'] }}', '{{ order['modal'] }}', '{{ order['pembulatan'] }}', '{{ order['metode_bayar'] }}', '{{ order['status_bayar'] }}', '{{ order['jumlah_dp'] }}')" class="btn-sm btn-edit-sm">Edit</button>
                                    <a href="/delete/{{ order['id'] }}" onclick="return confirm('Hapus order ini?')" class="btn-sm btn-delete-sm">Hapus</a>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr><td colspan="9" style="text-align:center; color:#999; padding:20px;">Belum ada data transaksi di periode ini.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        {% else %}
        <!-- HALAMAN OPERASIONAL -->
        <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px;">
            <div class="card">
                <h2>Catat Pengeluaran</h2>
                <form action="/add_expense" method="POST">
                    <div class="form-group">
                        <label>Keterangan Pengeluaran</label>
                        <input type="text" name="keterangan" placeholder="Masukkan Pengeluaran" required>
                    </div>
                    <div class="form-group">
                        <label>Jumlah Biaya (Rp)</label>
                        <input type="number" name="jumlah" placeholder="0" required>
                    </div>
                    <button type="submit" style="width: 100%; margin-top: 10px; background:#f39c12;">Simpan</button>
                </form>
            </div>

            <div class="card">
                <h2>Riwayat Pengeluaran</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Tgl</th>
                            <th>Keterangan</th>
                            <th>Jumlah Biaya</th>
                            <th>Aksi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for exp in expenses %}
                        <tr>
                            <td>{{ exp['tanggal'][:10] }}</td>
                            <td><b>{{ exp['keterangan'] }}</b></td>
                            <td style="color:#dd4b39; font-weight:bold;">Rp {{ "{:,.0f}".format(exp['jumlah']).replace(",", ".") }}</td>
                            <td>
                                <a href="/delete_expense/{{ exp['id'] }}" onclick="return confirm('Hapus pengeluaran ini?')" class="btn-sm btn-delete-sm">Hapus</a>
                            </td>
                        </tr>
                        {% else %}
                        <tr><td colspan="4" style="text-align:center; color:#999;">Belum ada pengeluaran dicatat.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}
    </div>
</div>

<!-- MODAL POP-UP TAMBAH TRANSAKSI BARU -->
<div id="tambahModal" class="modal-overlay">
    <div class="modal-content">
        <h2 style="margin-top:0; border-bottom:1px solid #eee; padding-bottom:8px;">Tambah Transaksi</h2>
        <form action="/add" method="POST">
            <div class="form-group">
                <label>No. Order</label>
                <input type="text" name="kode_order" value="{{ auto_kode_order }}">
            </div>
            <div class="form-group">
                <label>Nama Pelanggan</label>
                <input type="text" name="nama_pelanggan" placeholder="Masukkan nama pelanggan" required>
            </div>
            <div class="form-group">
                <label>Detail Pesanan</label>
                <input type="text" name="nama_pesanan" placeholder="Masukkan detail pesanan" required>
            </div>
            <div style="display:flex; gap:10px;">
                <div class="form-group" style="flex:1;">
                    <label>Qty</label>
                    <input type="number" id="tb_qty" name="qty" value="1" min="1" oninput="hitKalkulasiTambah()" required>
                </div>
                <div class="form-group" style="flex:2;">
                    <label>Harga Jual Total (Rp)</label>
                    <input type="number" id="tb_omset" name="omset" placeholder="0" oninput="hitKalkulasiTambah()" required>
                </div>
            </div>
            <div style="display:flex; gap:10px;">
                <div class="form-group" style="flex:1;">
                    <label>Modal Bahan (Rp)</label>
                    <input type="number" id="tb_modal" name="modal" placeholder="0" oninput="hitKalkulasiTambah()" required>
                </div>
                <div class="form-group" style="flex:1;">
                    <label>Pembulatan (Rp)</label>
                    <input type="number" id="tb_pembulatan" name="pembulatan" value="0">
                </div>
            </div>
            <div class="form-group">
                <label>Status Pembayaran</label>
                <select id="tb_status_bayar" name="status_bayar" onchange="toggleDPTambah()">
                    <option value="LUNAS">LUNAS</option>
                    <option value="DP">DP / Belum Lunas</option>
                </select>
            </div>
            <div class="form-group" id="tb_box_dp" style="display:none;">
                <label>Jumlah DP (Rp)</label>
                <input type="number" id="tb_jumlah_dp" name="jumlah_dp" value="0" oninput="hitKalkulasiTambah()">
            </div>
            <div class="form-group">
                <label>Metode Pembayaran</label>
                <select name="metode_bayar">
                    <option value="Cash">Cash / Tunai</option>
                    <option value="QRIS">QRIS</option>
                    <option value="Transfer">Transfer Bank</option>
                </select>
            </div>

            <div class="calculated-box">
                Estimasi Laba: <span id="tb_laba_text">Rp 0</span><br>
                <small id="tb_sisa_text" style="color:#dd4b39;"></small>
            </div>

            <div style="display:flex; gap:10px; margin-top:15px;">
                <button type="submit" style="flex:1;">Simpan Transaksi</button>
                <button type="button" onclick="closeTambahModal()" style="flex:1; background:#95a5a6;">Batal</button>
            </div>
        </form>
    </div>
</div>

<!-- MODAL EDIT DATA ORDER -->
<div id="editModal" class="modal-overlay">
    <div class="modal-content">
        <h2 style="margin-top:0; border-bottom:1px solid #eee; padding-bottom:8px;">Edit Transaksi</h2>
        <form id="editForm" action="/edit" method="POST">
            <input type="hidden" id="edit_id" name="id">
            <div class="form-group">
                <label>No. Order</label>
                <input type="text" id="edit_kode" name="kode_order" required>
            </div>
            <div class="form-group">
                <label>Nama Pelanggan</label>
                <input type="text" id="edit_pelanggan" name="nama_pelanggan" required>
            </div>
            <div class="form-group">
                <label>Detail Pesanan</label>
                <input type="text" id="edit_pesanan" name="nama_pesanan" required>
            </div>
            <div style="display:flex; gap:10px;">
                <div class="form-group" style="flex:1;">
                    <label>Qty</label>
                    <input type="number" id="edit_qty" name="qty" required>
                </div>
                <div class="form-group" style="flex:2;">
                    <label>Total Harga / Omset (Rp)</label>
                    <input type="number" id="edit_omset" name="omset" required>
                </div>
            </div>
            <div style="display:flex; gap:10px;">
                <div class="form-group" style="flex:1;">
                    <label>Modal Bahan (Rp)</label>
                    <input type="number" id="edit_modal" name="modal" required>
                </div>
                <div class="form-group" style="flex:1;">
                    <label>Pembulatan (Rp)</label>
                    <input type="number" id="edit_pembulatan" name="pembulatan">
                </div>
            </div>
            <div class="form-group">
                <label>Status Pembayaran</label>
                <select id="edit_status" name="status_bayar">
                    <option value="LUNAS">LUNAS</option>
                    <option value="DP">DP / Belum Lunas</option>
                </select>
            </div>
            <div class="form-group">
                <label>Jumlah DP (Rp)</label>
                <input type="number" id="edit_dp" name="jumlah_dp">
            </div>
            <div class="form-group">
                <label>Metode Pembayaran</label>
                <select id="edit_metode" name="metode_bayar">
                    <option value="Cash">Cash / Tunai</option>
                    <option value="QRIS">QRIS</option>
                    <option value="Transfer">Transfer Bank</option>
                </select>
            </div>
            <div style="display:flex; gap:10px; margin-top:15px;">
                <button type="submit" style="flex:1;">Simpan Perubahan</button>
                <button type="button" onclick="closeEditModal()" style="flex:1; background:#95a5a6;">Batal</button>
            </div>
        </form>
    </div>
</div>

<!-- LAYOUT STRUK CETAK NOTA PERCETAKAN -->
<div id="struk-printable" style="display:none;">
    <div style="text-align: center; margin-bottom: 6px;">
        <img src="/static/logo.png" style="max-width: 45mm; height: auto; filter: grayscale(100%); display: block; margin: 0 auto;">
    </div>

    <div class="p-warning">
        Jl. Cemara RT 05, Jotawang, Bangunharjo, Kec. Sewon<br>
        Kabupaten Bantul, Daerah Istimewa Yogyakarta 55187
    </div>

    <div class="p-warning">
        Telp 085800570141
    </div>

    <div class="p-line"></div>

    <table style="width: 100%; font-size: 7.5pt; border-collapse: collapse; margin: 2px 0;">
        <tr>
            <td style="width: 75px; padding: 1px 0;">No Order</td>
            <td style="width: 10px; text-align: center; padding: 1px 0;">:</td>
            <td style="padding: 1px 0;"><b id="st-kode"></b></td>
        </tr>
        <tr>
            <td style="padding: 1px 0;">Tanggal</td>
            <td style="text-align: center; padding: 1px 0;">:</td>
            <td style="padding: 1px 0;"><span id="st-tgl"></span></td>
        </tr>
        <tr>
            <td style="padding: 1px 0;">Pelanggan</td>
            <td style="text-align: center; padding: 1px 0;">:</td>
            <td style="padding: 1px 0;"><b id="st-pelanggan"></b></td>
        </tr>
    </table>

    <div class="p-line"></div>

    <table class="p-table">
        <thead>
            <tr>
                <th>Produk</th>
                <th class="text-right">Harga</th>
                <th class="text-center">Qty</th>
                <th class="text-right">Total</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td id="st-pesanan"></td>
                <td class="text-right" id="st-harga-satuan"></td>
                <td class="text-center" id="st-qty"></td>
                <td class="text-right" id="st-total"></td>
            </tr>
        </tbody>
    </table>

    <div class="p-line"></div>

    <div class="p-row"><span>Pembulatan :</span><span id="st-pembulatan">0</span></div>
    <div class="p-row"><span>Total :</span><b id="st-grandtotal"></b></div>
    <div class="p-row" id="st-box-dp" style="display:none;"><span>DP / Bayar :</span><span id="st-dp">0</span></div>
    <div class="p-row" id="st-box-sisa" style="display:none;"><span>Sisa Tagihan :</span><b id="st-sisa">0</b></div>
    <div class="p-row"><span>Metode Bayar :</span><span id="st-metode"></span></div>

    <div class="p-line"></div>

    <div class="text-center" style="margin-top: 8px;">
        <b>TERIMA KASIH ATAS PESANANNYA</b><br>
    </div>
</div>

<script>
    function openTambahModal() {
        document.getElementById('tambahModal').style.display = 'flex';
    }

    function closeTambahModal() {
        document.getElementById('tambahModal').style.display = 'none';
    }

    function toggleDPTambah() {
        const st = document.getElementById('tb_status_bayar').value;
        document.getElementById('tb_box_dp').style.display = (st === 'DP') ? 'block' : 'none';
        hitKalkulasiTambah();
    }

    function hitKalkulasiTambah() {
        const omset = parseFloat(document.getElementById('tb_omset').value) || 0;
        const modal = parseFloat(document.getElementById('tb_modal').value) || 0;
        const dp = parseFloat(document.getElementById('tb_jumlah_dp').value) || 0;
        const st = document.getElementById('tb_status_bayar').value;

        document.getElementById('tb_laba_text').innerText = 'Rp ' + (omset - modal).toLocaleString('id-ID');
        
        if (st === 'DP') {
            const sisa = omset - dp;
            document.getElementById('tb_sisa_text').innerText = 'Sisa Tagihan: Rp ' + sisa.toLocaleString('id-ID');
        } else {
            document.getElementById('tb_sisa_text').innerText = '';
        }
    }

    function filterTable(inputId, tableId) {
        const input = document.getElementById(inputId);
        const filter = input.value.toLowerCase();
        const table = document.getElementById(tableId);
        const tr = table.getElementsByTagName("tr");

        for (let i = 1; i < tr.length; i++) {
            let match = false;
            const td = tr[i].getElementsByTagName("td");
            for (let j = 0; j < td.length - 1; j++) {
                if (td[j] && td[j].innerText.toLowerCase().indexOf(filter) > -1) {
                    match = true;
                    break;
                }
            }
            tr[i].style.display = match ? "" : "none";
        }
    }

    function kirimWA(pelanggan, pesanan, omset, status, sisa) {
        let msg = `Halo Kak *${pelanggan}*, Terima kasih telah order di *Aditiya Grafika*!%0A%0A` +
                  `*Detail Pesanan:* ${pesanan}%0A` +
                  `*Total:* Rp ${parseFloat(omset).toLocaleString('id-ID')}%0A` +
                  `*Status:* ${status}%0A`;
        if (status === 'DP') {
            msg += `*Sisa Pembayaran:* Rp ${parseFloat(sisa).toLocaleString('id-ID')}%0A`;
        }
        msg += `%0APesanan Kakak sedang kami proses ya!`;
        
        // Menggunakan web.whatsapp.com agar langsung bypass halaman konfirmasi
        window.open(`https://web.whatsapp.com/send?text=${msg}`, '_blank');
    }
    function cetakStruk(kode, pelanggan, pesanan, qty, omset, pembulatan, metode, tanggal, status, dp, sisa) {
        document.getElementById('st-kode').innerText = kode;
        document.getElementById('st-tgl').innerText = tanggal.substring(0, 16);
        document.getElementById('st-pelanggan').innerText = pelanggan;
        document.getElementById('st-pesanan').innerText = pesanan;
        document.getElementById('st-qty').innerText = qty;
        
        const pricePerUnit = parseFloat(omset) / parseFloat(qty || 1);
        document.getElementById('st-harga-satuan').innerText = pricePerUnit.toLocaleString('id-ID');
        document.getElementById('st-total').innerText = parseFloat(omset).toLocaleString('id-ID');
        document.getElementById('st-pembulatan').innerText = parseFloat(pembulatan || 0).toLocaleString('id-ID');
        document.getElementById('st-grandtotal').innerText = 'Rp ' + parseFloat(omset).toLocaleString('id-ID');
        document.getElementById('st-metode').innerText = metode;

        if (status === 'DP') {
            document.getElementById('st-box-dp').style.display = 'flex';
            document.getElementById('st-box-sisa').style.display = 'flex';
            document.getElementById('st-dp').innerText = 'Rp ' + parseFloat(dp).toLocaleString('id-ID');
            document.getElementById('st-sisa').innerText = 'Rp ' + parseFloat(sisa).toLocaleString('id-ID');
        } else {
            document.getElementById('st-box-dp').style.display = 'none';
            document.getElementById('st-box-sisa').style.display = 'none';
        }

        const strukArea = document.getElementById('struk-printable');
        strukArea.style.display = 'block';
        window.print();
        strukArea.style.display = 'none';
    }

    function openEditModal(id, kode, pelanggan, pesanan, qty, omset, modal, pembulatan, metode, status, dp) {
        document.getElementById('edit_id').value = id;
        document.getElementById('edit_kode').value = kode;
        document.getElementById('edit_pelanggan').value = pelanggan;
        document.getElementById('edit_pesanan').value = pesanan;
        document.getElementById('edit_qty').value = qty;
        document.getElementById('edit_omset').value = omset;
        document.getElementById('edit_modal').value = modal;
        document.getElementById('edit_pembulatan').value = pembulatan;
        document.getElementById('edit_metode').value = metode;
        document.getElementById('edit_status').value = status;
        document.getElementById('edit_dp').value = dp;
        document.getElementById('editModal').style.display = 'flex';
    }

    function closeEditModal() {
        document.getElementById('editModal').style.display = 'none';
    }
</script>

</body>
</html>
'''

@app.route('/')
def index():
    active_menu = request.args.get('menu', 'dashboard')
    bulan_pilihan = request.args.get('bulan', datetime.now().strftime('%Y-%m'))
    auto_kode_order = generate_kode_order()
    datetime_now_format = datetime.now().strftime('%d %B %Y')
    
    bulan_nama_map = {
        '01': 'Januari', '02': 'Februari', '03': 'Maret', '04': 'April',
        '05': 'Mei', '06': 'Juni', '07': 'Juli', '08': 'Agustus',
        '09': 'September', '10': 'Oktober', '11': 'November', '12': 'Desember'
    }
    
    try:
        thn, bln = bulan_pilihan.split('-')
        nama_bulan_indo = f"{bulan_nama_map.get(bln, bln)} {thn}"
    except:
        nama_bulan_indo = bulan_pilihan

    conn = get_db()
    cursor = conn.cursor()
    
    if active_menu == 'dashboard':
        cursor.execute("SELECT * FROM orders WHERE strftime('%Y-%m', tanggal) = ? ORDER BY id DESC", (bulan_pilihan,))
        orders = cursor.fetchall()
        cursor.execute("SELECT * FROM expenses WHERE strftime('%Y-%m', tanggal) = ?", (bulan_pilihan,))
        expenses = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM expenses ORDER BY id DESC")
        expenses = cursor.fetchall()
        orders = []

    total_omset = sum(o['omset'] for o in orders)
    total_modal = sum(o['modal'] for o in orders)
    total_ops = sum(e['jumlah'] for e in expenses)
    laba_bersih_riil = total_omset - total_modal - total_ops
    
    conn.close()
    
    return render_template_string(
        HTML_TEMPLATE, 
        orders=orders, 
        expenses=expenses,
        total_omset=total_omset, 
        total_modal=total_modal, 
        total_ops=total_ops,
        laba_bersih_riil=laba_bersih_riil, 
        bulan_pilihan=bulan_pilihan,
        nama_bulan_indo=nama_bulan_indo,
        active_menu=active_menu,
        auto_kode_order=auto_kode_order,
        datetime_now_format=datetime_now_format
    )

@app.route('/add', methods=['POST'])
def add_order():
    kode_order = request.form.get('kode_order')
    if not kode_order:
        kode_order = generate_kode_order()
        
    nama_pelanggan = request.form['nama_pelanggan']
    nama_pesanan = request.form['nama_pesanan']
    qty = int(request.form.get('qty', 1))
    omset = int(request.form['omset'])
    modal = int(request.form['modal'])
    pembulatan = int(request.form.get('pembulatan', 0))
    status_bayar = request.form['status_bayar']
    jumlah_dp = int(request.form.get('jumlah_dp', 0)) if status_bayar == 'DP' else 0
    sisa_bayar = omset - jumlah_dp if status_bayar == 'DP' else 0
    metode_bayar = request.form['metode_bayar']
    laba = omset - modal

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (kode_order, nama_pelanggan, nama_pesanan, qty, omset, modal, laba, pembulatan, status_bayar, jumlah_dp, sisa_bayar, metode_bayar)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (kode_order, nama_pelanggan, nama_pesanan, qty, omset, modal, laba, pembulatan, status_bayar, jumlah_dp, sisa_bayar, metode_bayar))
    conn.commit()
    conn.close()
    return redirect(url_for('index', menu='dashboard'))

@app.route('/pelunasan/<int:id>')
def pelunasan(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status_bayar = 'LUNAS', sisa_bayar = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/add_expense', methods=['POST'])
def add_expense():
    keterangan = request.form['keterangan']
    jumlah = int(request.form['jumlah'])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expenses (keterangan, jumlah) VALUES (?, ?)", (keterangan, jumlah))
    conn.commit()
    conn.close()
    return redirect(url_for('index', menu='pengeluaran'))

@app.route('/delete_expense/<int:id>')
def delete_expense(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', menu='pengeluaran'))

@app.route('/edit', methods=['POST'])
def edit_order():
    order_id = request.form['id']
    kode_order = request.form['kode_order']
    nama_pelanggan = request.form['nama_pelanggan']
    nama_pesanan = request.form['nama_pesanan']
    qty = int(request.form.get('qty', 1))
    omset = int(request.form['omset'])
    modal = int(request.form['modal'])
    pembulatan = int(request.form.get('pembulatan', 0))
    status_bayar = request.form['status_bayar']
    jumlah_dp = int(request.form.get('jumlah_dp', 0)) if status_bayar == 'DP' else 0
    sisa_bayar = omset - jumlah_dp if status_bayar == 'DP' else 0
    metode_bayar = request.form['metode_bayar']
    laba = omset - modal

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders 
        SET kode_order=?, nama_pelanggan=?, nama_pesanan=?, qty=?, omset=?, modal=?, laba=?, pembulatan=?, status_bayar=?, jumlah_dp=?, sisa_bayar=?, metode_bayar=?
        WHERE id=?
    ''', (kode_order, nama_pelanggan, nama_pesanan, qty, omset, modal, laba, pembulatan, status_bayar, jumlah_dp, sisa_bayar, metode_bayar, order_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/delete/<int:id>')
def delete_order(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/backup')
def backup_db():
    try:
        db_path = get_resource_path(DB_NAME)
        if not os.path.exists(db_path):
            return "File database tidak ditemukan!", 404
            
        backup_filename = f'Backup_AditiyaGrafika_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        return send_file(
            db_path, 
            as_attachment=True, 
            download_name=backup_filename,
            mimetype='application/x-sqlite3'
        )
    except Exception as e:
        return f"Gagal membuat backup: {str(e)}", 500

@app.route('/export/excel')
def export_excel():
    bulan_pilihan = request.args.get('bulan', datetime.now().strftime('%Y-%m'))
    conn = get_db()
    df = pd.read_sql_query("SELECT kode_order AS No_Order, tanggal AS Tanggal, nama_pelanggan AS Pelanggan, nama_pesanan AS Pesanan, qty AS Qty, omset AS Omset, modal AS Modal, laba AS Laba, status_bayar AS Status, jumlah_dp AS DP, sisa_bayar AS Sisa_Tagihan, metode_bayar AS Metode FROM orders WHERE strftime('%Y-%m', tanggal) = ? ORDER BY id ASC", conn, params=(bulan_pilihan,))
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f'Laporan_{bulan_pilihan}')
    
    output.seek(0)
    return send_file(output, download_name=f'Laporan_Penjualan_{bulan_pilihan}.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export/pdf')
def export_pdf():
    bulan_pilihan = request.args.get('bulan', datetime.now().strftime('%Y-%m'))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE strftime('%Y-%m', tanggal) = ? ORDER BY id ASC", (bulan_pilihan,))
    orders = cursor.fetchall()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, alignment=1, spaceAfter=10)
    
    elements.append(Paragraph(f"<b>LAPORAN PENJUALAN - ADITIYA GRAFIKA ({bulan_pilihan})</b>", title_style))
    elements.append(Spacer(1, 10))

    data = [["No. Order", "Tanggal", "Pelanggan", "Pesanan", "Qty", "Omset", "Status"]]
    t_omset = 0
    for o in orders:
        data.append([
            str(o['kode_order']),
            o['tanggal'][:10],
            o['nama_pelanggan'],
            o['nama_pesanan'],
            str(o['qty']),
            f"Rp {o['omset']:,}",
            o['status_bayar']
        ])
        t_omset += o['omset']

    data.append(["", "", "", "TOTAL", "", f"Rp {t_omset:,}", ""])

    table = Table(data, colWidths=[80, 55, 90, 140, 30, 75, 55])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (5,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#ecf0f1')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name=f'Laporan_Penjualan_{bulan_pilihan}.pdf', as_attachment=True, mimetype='application/pdf')

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    init_db()
    print("Aplikasi Aditiya Grafika berjalan di http://127.0.0.1:5000")
    Timer(1.2, open_browser).start()
    app.run(debug=False)