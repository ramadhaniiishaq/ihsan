from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
import bcrypt
from functools import wraps
from datetime import datetime, date
from secrets import token_hex


app = Flask(__name__)
app.secret_key=token_hex(16)
app.config['MYSQL_CURSORCLASS']='DictCursor'
app.config['MYSQL_HOST']='localhost'
app.config['MYSQL_USER']='root'
app.config['MYSQL_PASSWORD']=''
app.config['MYSQL_DB']='db_sholat'
app.config['UPLOAD_FOLDER']='static/uploads'
mysql = MySQL(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Silakan login terlebih dahulu', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('halaman_wali'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE username = %s", (username,))
        admin = cur.fetchone()
        cur.close()
        
        if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password'].encode('utf-8')):
            session['logged_in'] = True
            session['username'] = admin['username']
            session['admin_id'] = admin['id_admin']
            flash('Login berhasil!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah!', 'danger')
    
    return render_template('login.html')
@app.route('/seeder')
def seeder():
    username = 'admin'
    password = 'admin123'
    
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT IGNORE INTO admin (username,password) VALUES (%s,%s)",
        (username, hashed.decode('utf-8'))
    )
    mysql.connection.commit()
    cursor.close()
    
    return "Seeder berhasil dijalankan"

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah logout', 'info')
    return redirect(url_for('halaman_wali'))

@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    
    # Get statistics
    cur.execute("SELECT COUNT(*) as total_siswa FROM siswa")
    total_siswa = cur.fetchone()['total_siswa']
    
    cur.execute("SELECT COUNT(*) as total_kelas FROM kelas")
    total_kelas = cur.fetchone()['total_kelas']
    
    cur.execute("""
        SELECT COUNT(*) as total_absensi 
        FROM absensi_sholat 
        WHERE tanggal = CURDATE()
    """)
    total_absensi = cur.fetchone()['total_absensi']
    
    # Today's attendance by prayer
    cur.execute("""
        SELECT s.nama_sholat, 
               COUNT(CASE WHEN a.status = 'sholat' THEN 1 END) as hadir,
               COUNT(CASE WHEN a.status = 'halangan' THEN 1 END) as halangan,
               COUNT(CASE WHEN a.status = 'tidak_sholat' THEN 1 END) as tidak
        FROM sholat s
        LEFT JOIN absensi_sholat a ON s.id_sholat = a.id_sholat AND a.tanggal = CURDATE()
        GROUP BY s.id_sholat, s.nama_sholat
    """)
    chart_data = cur.fetchall()
    
    cur.close()
    
    return render_template('admin/dashboard.html', 
                         total_siswa=total_siswa,
                         total_kelas=total_kelas,
                         total_absensi=total_absensi,
                         chart_data=chart_data)

@app.route('/absensi', methods=['GET', 'POST'])
@login_required
def absensi():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        siswa_id = request.form['siswa_id']
        sholat_id = request.form['sholat_id']
        status = request.form['status']
        tanggal = request.form['tanggal']
        
        # Check if attendance already exists
        cur.execute("""
            SELECT * FROM absensi_sholat 
            WHERE siswa_id = %s AND id_sholat = %s AND tanggal = %s
        """, (siswa_id, sholat_id, tanggal))
        
        existing = cur.fetchone()
        
        if existing:
            cur.execute("""
                UPDATE absensi_sholat 
                SET status = %s 
                WHERE siswa_id = %s AND id_sholat = %s AND tanggal = %s
            """, (status, siswa_id, sholat_id, tanggal))
            flash('Data absensi berhasil diupdate!', 'success')
        else:
            cur.execute("""
                INSERT INTO absensi_sholat (siswa_id, id_sholat, tanggal, status)
                VALUES (%s, %s, %s, %s)
            """, (siswa_id, sholat_id, tanggal, status))
            flash('Data absensi berhasil ditambahkan!', 'success')
        
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('absensi'))
    
    # GET request - display form
    cur.execute("SELECT * FROM siswa ORDER BY nama_siswa")
    siswa_list = cur.fetchall()
    
    cur.execute("SELECT * FROM sholat ORDER BY id_sholat")
    sholat_list = cur.fetchall()
    
    cur.execute("""
        SELECT a.*, s.nama_siswa, sh.nama_sholat, k.nama_kelas
        FROM absensi_sholat a
        JOIN siswa s ON a.siswa_id = s.id_siswa
        JOIN sholat sh ON a.id_sholat = sh.id_sholat
        JOIN kelas k ON s.id_kelas = k.id_kelas
        WHERE a.tanggal = CURDATE()
        ORDER BY a.tanggal DESC, s.nama_siswa
    """)
    today_absensi = cur.fetchall()
    
    cur.close()
    
    return render_template('admin/absensi.html', 
                         siswa_list=siswa_list,
                         sholat_list=sholat_list,
                         today_absensi=today_absensi,
                         today_date=date.today())

@app.route('/siswa', methods=['GET', 'POST'])
@login_required
def siswa():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        nama_siswa = request.form['nama_siswa']
        id_kelas = request.form['id_kelas']
        Nis=request.form['nis']
        
        cur.execute("""
            INSERT INTO siswa (nama_siswa, id_kelas, nis)
            VALUES (%s, %s, %s)
        """, (nama_siswa, id_kelas, Nis))
        mysql.connection.commit()
        flash('Data siswa berhasil ditambahkan!', 'success')
        return redirect(url_for('siswa'))
    
    # GET request
    cur.execute("""
        SELECT s.*, k.nama_kelas 
        FROM siswa s
        JOIN kelas k ON s.id_kelas = k.id_kelas
        ORDER BY s.nama_siswa
    """)
    siswa_list = cur.fetchall()
    
    cur.execute("SELECT * FROM kelas ORDER BY nama_kelas")
    kelas_list = cur.fetchall()
    
    cur.close()
    
    return render_template('admin/siswa.html', siswa_list=siswa_list, kelas_list=kelas_list)

@app.route('/siswa/edit/<int:id>', methods=['POST'])
@login_required
def edit_siswa(id):
    nama_siswa = request.form['nama_siswa']
    id_kelas = request.form['id_kelas']
    Nis=request.form['nis']
    
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE siswa SET nama_siswa = %s, id_kelas = %s ,nis=%s
        WHERE id_siswa = %s
    """, (nama_siswa, id_kelas, Nis, id))
    mysql.connection.commit()
    cur.close()
    
    flash('Data siswa berhasil diupdate!', 'success')
    return redirect(url_for('siswa'))

@app.route('/siswa/delete/<int:id>')
@login_required
def delete_siswa(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM siswa WHERE id_siswa = %s", (id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Data siswa berhasil dihapus!', 'success')
    return redirect(url_for('siswa'))

@app.route('/kelas', methods=['GET', 'POST'])
@login_required
def kelas():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        nama_kelas = request.form['nama_kelas']
        
        cur.execute("INSERT INTO kelas (nama_kelas) VALUES (%s)", (nama_kelas,))
        mysql.connection.commit()
        flash('Data kelas berhasil ditambahkan!', 'success')
        return redirect(url_for('kelas'))
    
    cur.execute("SELECT * FROM kelas ORDER BY nama_kelas")
    kelas_list = cur.fetchall()
    cur.close()
    
    return render_template('admin/kelas.html', kelas_list=kelas_list)

@app.route('/kelas/edit/<int:id>', methods=['POST'])
@login_required
def edit_kelas(id):
    nama_kelas = request.form['nama_kelas']
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE kelas SET nama_kelas = %s WHERE id_kelas = %s", (nama_kelas, id))
    mysql.connection.commit()
    cur.close()
    
    flash('Data kelas berhasil diupdate!', 'success')
    return redirect(url_for('kelas'))

@app.route('/kelas/delete/<int:id>')
@login_required
def delete_kelas(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM kelas WHERE id_kelas = %s", (id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Data kelas berhasil dihapus!', 'success')
    return redirect(url_for('kelas'))

@app.route('/laporan')
@login_required
def laporan():
    cur = mysql.connection.cursor()
    
    cur.execute("""
        SELECT a.*, s.nama_siswa, k.nama_kelas, sh.nama_sholat
        FROM absensi_sholat a
        JOIN siswa s ON a.siswa_id = s.id_siswa
        JOIN kelas k ON s.id_kelas = k.id_kelas
        JOIN sholat sh ON a.id_sholat = sh.id_sholat
        ORDER BY a.tanggal DESC, s.nama_siswa
    """)
    all_absensi = cur.fetchall()
    
    cur.execute("SELECT * FROM kelas ORDER BY nama_kelas")
    kelas_list = cur.fetchall()
    
    cur.execute("SELECT * FROM sholat ORDER BY id_sholat")
    sholat_list = cur.fetchall()
    
    cur.close()
    
    return render_template('admin/laporan.html', 
                         all_absensi=all_absensi,
                         kelas_list=kelas_list,
                         sholat_list=sholat_list)

@app.route('/laporan/filter', methods=['POST'])
@login_required
def filter_laporan():
    tanggal_mulai = request.form.get('tanggal_mulai')
    tanggal_akhir = request.form.get('tanggal_akhir')
    id_kelas = request.form.get('id_kelas')
    id_sholat = request.form.get('id_sholat')
    
    cur = mysql.connection.cursor()
    
    query = """
        SELECT a.*, s.nama_siswa, k.nama_kelas, sh.nama_sholat
        FROM absensi_sholat a
        JOIN siswa s ON a.siswa_id = s.id_siswa
        JOIN kelas k ON s.id_kelas = k.id_kelas
        JOIN sholat sh ON a.id_sholat = sh.id_sholat
        WHERE 1=1
    """
    params = []
    
    if tanggal_mulai and tanggal_akhir:
        query += " AND a.tanggal BETWEEN %s AND %s"
        params.extend([tanggal_mulai, tanggal_akhir])
    
    if id_kelas and id_kelas != '':
        query += " AND s.id_kelas = %s"
        params.append(id_kelas)
    
    if id_sholat and id_sholat != '':
        query += " AND a.id_sholat = %s"
        params.append(id_sholat)
    
    query += " ORDER BY a.tanggal DESC, s.nama_siswa"
    
    cur.execute(query, params)
    filtered_data = cur.fetchall()
    cur.close()
    
    return render_template('admin/laporan_filtered.html', absensi=filtered_data)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT password FROM admin WHERE id_admin = %s", (session['admin_id'],))
        admin = cur.fetchone()
        
        if bcrypt.checkpw(current_password.encode('utf-8'), admin['password'].encode('utf-8')):
            if new_password == confirm_password:
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                cur.execute("UPDATE admin SET password = %s WHERE id_admin = %s", 
                        (hashed_password.decode('utf-8'), session['admin_id']))
                mysql.connection.commit()
                flash('Password berhasil diubah!', 'success')
            else:
                flash('Password baru tidak cocok!', 'danger')
        else:
            flash('Password saat ini salah!', 'danger')
        
        cur.close()
        return redirect(url_for('profile'))
    
    return render_template('admin/profile.html', username=session['username'])

@app.route('/wali')
def halaman_wali():
    return render_template('halaman_wali.html')

@app.route('/wali/cari', methods=['POST'])
def wali_cari_siswa():
    nis = request.form.get('nis', '').strip()
    
    if not nis:
        flash('Silakan masukkan NIS siswa yang ingin dicari', 'warning')
        return redirect(url_for('halaman_wali'))
    
    cur = mysql.connection.cursor()
    
    cur.execute("""
        SELECT s.id_siswa, s.nama_siswa, s.nis, k.nama_kelas
        FROM siswa s
        JOIN kelas k ON s.id_kelas = k.id_kelas
        WHERE s.nis LIKE %s
        ORDER BY s.nama_siswa
        LIMIT 5
    """, (f'%{nis}%',))
    
    hasil_pencarian = cur.fetchall()
    cur.close()
    
    if not hasil_pencarian:
        flash(f'Tidak ditemukan siswa dengan NIS "{nis}"', 'danger')
        return redirect(url_for('halaman_wali'))

    session['hasil_cari_siswa'] = [dict(row) for row in hasil_pencarian]
    
    return redirect(url_for('wali_hasil_pencarian'))

@app.route('/wali/hasil')
def wali_hasil_pencarian():
    hasil_pencarian = session.get('hasil_cari_siswa', [])
    if not hasil_pencarian:
        return redirect(url_for('halaman_wali'))
    
    return render_template('wali_hasil.html', siswa_list=hasil_pencarian)
@app.route('/wali/detail/<int:siswa_id>')
def wali_detail_siswa(siswa_id):
    siswa_id = int(siswa_id)
    cur = mysql.connection.cursor()
    
    cur.execute("""
        SELECT s.id_siswa, s.nama_siswa, s.nis, k.nama_kelas
        FROM siswa s
        JOIN kelas k ON s.id_kelas = k.id_kelas
        WHERE s.id_siswa = %s
    """, (siswa_id,))
    siswa = cur.fetchone()
    
    if not siswa:
        flash('Data siswa tidak ditemukan', 'danger')
        return redirect(url_for('halaman_wali'))

    current_month = datetime.today().month
    current_year = datetime.today().year
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'sholat' THEN 1 ELSE 0 END) as hadir,
            SUM(CASE WHEN status = 'halangan' THEN 1 ELSE 0 END) as halangan,
            SUM(CASE WHEN status = 'tidak_sholat' THEN 1 ELSE 0 END) as tidak
        FROM absensi_sholat
        WHERE siswa_id = %s 
        AND MONTH(tanggal) = %s 
        AND YEAR(tanggal) = %s
    """, (siswa_id, current_month, current_year))
    statistik_bulan_ini = cur.fetchone()
    
    # Ubah datetime ke string
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    cur.execute("""
        SELECT 
            sh.nama_sholat,
            a.status,
            CASE 
                WHEN a.status = 'sholat' THEN '✅ Hadir'
                WHEN a.status = 'halangan' THEN '🚫 Halangan'
                WHEN a.status = 'tidak_sholat' THEN '❌ Tidak Hadir'
                ELSE 'Belum Absen'
            END as status_text
        FROM sholat sh
        LEFT JOIN absensi_sholat a ON sh.id_sholat = a.id_sholat 
            AND a.siswa_id = %s 
            AND a.tanggal = %s
        ORDER BY sh.id_sholat
    """, (siswa_id, today_str))
    absensi_hari_ini = cur.fetchall()

    cur.execute("""
        SELECT 
            a.tanggal,
            DATE_FORMAT(a.tanggal, '%%d/%%m/%%Y') as tanggal_str,
            sh.nama_sholat,
            a.status,
            CASE 
                WHEN a.status = 'sholat' THEN 'sholat'
                WHEN a.status = 'halangan' THEN 'halangan'
                ELSE 'Tidak sholat'
            END as status_text
        FROM absensi_sholat a
        JOIN sholat sh ON a.id_sholat = sh.id_sholat
        WHERE a.siswa_id = %s
        ORDER BY a.tanggal DESC, sh.id_sholat
        LIMIT 30
    """, (siswa_id,))
    riwayat_absensi = cur.fetchall()
    
    # PERBAIKAN: Query rekap bulanan dengan GROUP BY yang benar
    cur.execute("""
    SELECT 
        DATE_FORMAT(tanggal, '%%M %%Y') as bulan,
        YEAR(tanggal) as tahun,
        MONTH(tanggal) as bulan_num,
        COUNT(*) as total,
        SUM(CASE WHEN status = 'sholat' THEN 1 ELSE 0 END) as hadir,
        SUM(CASE WHEN status = 'halangan' THEN 1 ELSE 0 END) as halangan,
        SUM(CASE WHEN status = 'tidak_sholat' THEN 1 ELSE 0 END) as tidak,
        ROUND(SUM(CASE WHEN status = 'sholat' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),1) as persentase
    FROM absensi_sholat
    WHERE siswa_id = %s
    GROUP BY 
        YEAR(tanggal),
        MONTH(tanggal),
        DATE_FORMAT(tanggal, '%%M %%Y')
    ORDER BY tahun DESC, bulan_num DESC
    LIMIT 6
    """, (siswa_id,))
    rekap_bulanan = cur.fetchall()
    
    cur.close()
    
    return render_template('wali_detail.html', 
                         siswa=siswa,
                         statistik_bulan_ini=statistik_bulan_ini,
                         absensi_hari_ini=absensi_hari_ini,
                         riwayat_absensi=riwayat_absensi,
                         rekap_bulanan=rekap_bulanan,
                         today=today_str)  
if __name__ == '__main__':
    app.run(debug=True)