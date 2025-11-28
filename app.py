import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path

# ==================== CONFIGURACIÓN INICIAL ====================

# Configuración de la página
st.set_page_config(
    page_title="Finanzas Personales",
    page_icon="💰",
    layout="wide"
)

# Ruta de la base de datos
DB_PATH = "finanzas_personales.db"

# Categorías de gasto predefinidas
CATEGORIAS_GASTO = [
    "Alimentación",
    "Transporte",
    "Vivienda",
    "Salud",
    "Deseos",
    "Suscripciones",
    "Educación",
    "Deudas",
    "Ahorro",
    "Servicios",
    "Efectivo",
    "Mercado"
]


# ==================== FUNCIONES DE BASE DE DATOS Y BUCKETS ====================
def clasificar_bucket(categoria):
    """
    Clasifica la categoría en el bucket correspondiente.
    - 'Deseos' → Deseos
    - 'Ahorro' → Ahorro
    - Resto → Necesidades
    """
    if categoria.strip().lower() == "deseos":
        return "Deseos"
    elif categoria.strip().lower() == "ahorro":
        return "Ahorro"
    else:
        return "Necesidades"

def resumen_buckets(anio, mes):
    """
    Devuelve un dict con presupuesto, gastado y disponible para cada bucket en el periodo dado.
    - Para Necesidades y Deseos: disponible = presupuesto - gastado
    - Para Ahorro: solo se acumula lo asignado desde ingresos (no se descuenta por gastos)
    - Si quieres registrar retiros de ahorro, usa una categoría especial y descuéntala aquí.
    """
    ingresos = obtener_ingresos(anio, mes)
    gastos = obtener_gastos(anio, mes)

    presupuesto = {
        "Necesidades": ingresos["monto_necesidades"].sum() if not ingresos.empty else 0.0,
        "Deseos": ingresos["monto_deseos"].sum() if not ingresos.empty else 0.0,
        "Ahorro": ingresos["monto_ahorro"].sum() if not ingresos.empty else 0.0,
    }

    gastado = {"Necesidades": 0.0, "Deseos": 0.0, "Ahorro": 0.0}
    if not gastos.empty:
        gastos["bucket"] = gastos["categoria"].apply(clasificar_bucket)
        gastado["Necesidades"] = gastos[gastos["bucket"] == "Necesidades"]["valor"].sum()
        gastado["Deseos"] = gastos[gastos["bucket"] == "Deseos"]["valor"].sum()
        # Para ahorro, solo sumar si la categoría es 'Retiro de ahorro' (opcional)
        # gastado["Ahorro"] = gastos[gastos["categoria"].str.lower() == "retiro de ahorro"]["valor"].sum() if "retiro de ahorro" in gastos["categoria"].str.lower().values else 0.0
        gastado["Ahorro"] = 0.0  # Por defecto, no se descuenta nada de ahorro

    disponible = {
        "Necesidades": presupuesto["Necesidades"] - gastado["Necesidades"],
        "Deseos": presupuesto["Deseos"] - gastado["Deseos"],
        "Ahorro": presupuesto["Ahorro"]  # Solo se acumula
    }

    return {
        "presupuesto": presupuesto,
        "gastado": gastado,
        "disponible": disponible
    }

def inicializar_base_datos():
    """
    Crea la base de datos SQLite y las tablas si no existen.
    Se ejecuta automáticamente al iniciar la aplicación.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de INGRESOS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingresos (
            id_ingreso INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            concepto TEXT NOT NULL,
            valor_total REAL NOT NULL,
            porc_necesidades REAL NOT NULL,
            porc_deseos REAL NOT NULL,
            porc_ahorro REAL NOT NULL,
            monto_necesidades REAL NOT NULL,
            monto_deseos REAL NOT NULL,
            monto_ahorro REAL NOT NULL
        )
    """)
    
    # Tabla de GASTOS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id_gasto INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            concepto TEXT NOT NULL,
            valor REAL NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

def insertar_ingreso(fecha, concepto, valor_total, porc_necesidades, porc_deseos, porc_ahorro):
    """
    Inserta un nuevo ingreso en la base de datos con la distribución 80/10/10.
    """
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
    anio = fecha_obj.year
    mes = fecha_obj.month
    
    # Calcular montos según porcentajes
    monto_necesidades = valor_total * (porc_necesidades / 100)
    monto_deseos = valor_total * (porc_deseos / 100)
    monto_ahorro = valor_total * (porc_ahorro / 100)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO ingresos 
        (fecha, anio, mes, concepto, valor_total, porc_necesidades, porc_deseos, 
         porc_ahorro, monto_necesidades, monto_deseos, monto_ahorro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (fecha, anio, mes, concepto, valor_total, porc_necesidades, porc_deseos, 
          porc_ahorro, monto_necesidades, monto_deseos, monto_ahorro))
    
    conn.commit()
    conn.close()

def insertar_gasto(fecha, categoria, concepto, valor):
    """
    Inserta un nuevo gasto en la base de datos.
    """
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
    anio = fecha_obj.year
    mes = fecha_obj.month
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO gastos (fecha, anio, mes, categoria, concepto, valor)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (fecha, anio, mes, categoria, concepto, valor))
    
    conn.commit()
    conn.close()

def obtener_ingresos(anio=None, mes=None):
    """
    Obtiene los ingresos filtrados por año y mes (opcional).
    """
    conn = sqlite3.connect(DB_PATH)
    
    query = "SELECT * FROM ingresos"
    params = []
    
    if anio is not None and mes is not None:
        query += " WHERE anio = ? AND mes = ?"
        params = [anio, mes]
    elif anio is not None:
        query += " WHERE anio = ?"
        params = [anio]
    
    query += " ORDER BY fecha DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

def obtener_gastos(anio=None, mes=None):
    """
    Obtiene los gastos filtrados por año y mes (opcional).
    """
    conn = sqlite3.connect(DB_PATH)
    
    query = "SELECT * FROM gastos"
    params = []
    
    if anio is not None and mes is not None:
        query += " WHERE anio = ? AND mes = ?"
        params = [anio, mes]
    elif anio is not None:
        query += " WHERE anio = ?"
        params = [anio]
    
    query += " ORDER BY fecha DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

def eliminar_ingreso(id_ingreso):
    """
    Elimina un ingreso por su ID.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ingresos WHERE id_ingreso = ?", (id_ingreso,))
    conn.commit()
    conn.close()

def eliminar_gasto(id_gasto):
    """
    Elimina un gasto por su ID.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos WHERE id_gasto = ?", (id_gasto,))
    conn.commit()
    conn.close()

def obtener_anios_disponibles():
    """
    Obtiene la lista de años que tienen registros.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT anio FROM ingresos UNION SELECT DISTINCT anio FROM gastos ORDER BY anio DESC")
    anios = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return anios if anios else [datetime.now().year]

# ==================== INTERFAZ DE STREAMLIT ====================

# Inicializar la base de datos
inicializar_base_datos()

# Título principal
st.title("💰 Portal de Finanzas Personales")
st.markdown("Gestión de ingresos y gastos con la regla 80/10/10")
st.divider()

# Crear las pestañas principales
tab1, tab2, tab3 = st.tabs(["📊 Análisis General", "➕ Registrar Ingreso/Gasto", "🗑️ Eliminar Registros"])

# ==================== PESTAÑA 1: ANÁLISIS GENERAL ====================
with tab1:
    st.header("Análisis General")
    
    # Selector de período
    col1, col2 = st.columns([1, 2])
    
    with col1:
        anios_disponibles = obtener_anios_disponibles()
        anio_seleccionado = st.selectbox("Año", anios_disponibles, key="anio_analisis")
    
    with col2:
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        mes_seleccionado = st.selectbox("Mes", list(meses.keys()), 
                                        format_func=lambda x: meses[x],
                                        index=datetime.now().month - 1,
                                        key="mes_analisis")
    
    st.divider()
    
    # Obtener datos del período
    ingresos_periodo = obtener_ingresos(anio_seleccionado, mes_seleccionado)
    gastos_periodo = obtener_gastos(anio_seleccionado, mes_seleccionado)
    
    # Calcular totales
    total_ingresos = ingresos_periodo['valor_total'].sum() if not ingresos_periodo.empty else 0
    total_gastos = gastos_periodo['valor'].sum() if not gastos_periodo.empty else 0
    total_ahorro = ingresos_periodo['monto_ahorro'].sum() if not ingresos_periodo.empty else 0
    saldo_neto = total_ingresos - total_gastos - total_ahorro

    # Mostrar métricas principales
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Ingresos", f"${total_ingresos:,.2f}", help="Suma de todos los ingresos del período")

    with col2:
        st.metric("Total Gastos", f"${total_gastos:,.2f}", help="Suma de todos los gastos del período")

    with col3:
        delta_color = "normal" if saldo_neto >= 0 else "inverse"
        st.metric("Saldo Neto", f"${saldo_neto:,.2f}", 
                  delta=f"${abs(saldo_neto):,.2f}", 
                  delta_color=delta_color,
                  help="Diferencia entre ingresos, gastos y ahorro")
    
    st.divider()
    
    # Distribución 80/10/10
    if not ingresos_periodo.empty:
        st.subheader("📦 Distribución 80/10/10 (basada en ingresos)")
        
        total_necesidades = ingresos_periodo['monto_necesidades'].sum()
        total_deseos = ingresos_periodo['monto_deseos'].sum()
        total_ahorro = ingresos_periodo['monto_ahorro'].sum()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("💼 Necesidades", f"${total_necesidades:,.2f}",
                     help="Monto asignado para necesidades básicas")
            porc_nec = (total_necesidades / total_ingresos * 100) if total_ingresos > 0 else 0
            st.caption(f"📊 {porc_nec:.1f}% del ingreso total")
        
        with col2:
            st.metric("🎯 Deseos", f"${total_deseos:,.2f}",
                     help="Monto asignado para deseos y gustos")
            porc_des = (total_deseos / total_ingresos * 100) if total_ingresos > 0 else 0
            st.caption(f"📊 {porc_des:.1f}% del ingreso total")
        
        with col3:
            st.metric("🏦 Ahorro", f"${total_ahorro:,.2f}",
                     help="Monto asignado para ahorro")
            porc_aho = (total_ahorro / total_ingresos * 100) if total_ingresos > 0 else 0
            st.caption(f"📊 {porc_aho:.1f}% del ingreso total")
        
        st.divider()
    
    # Gastos por categoría
    if not gastos_periodo.empty:
        st.subheader("🏷️ Gastos por Categoría")
        
        gastos_por_categoria = gastos_periodo.groupby('categoria')['valor'].sum().sort_values(ascending=False)
        gastos_por_categoria_df = pd.DataFrame({
            'Categoría': gastos_por_categoria.index,
            'Monto': gastos_por_categoria.values,
            '% del Total': (gastos_por_categoria.values / total_gastos * 100).round(2)
        })
        
        # Mostrar tabla
        st.dataframe(
            gastos_por_categoria_df.style.format({
                'Monto': '${:,.2f}',
                '% del Total': '{:.2f}%'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Gráfico de barras
        st.bar_chart(gastos_por_categoria)
    else:
        st.info("No hay gastos registrados en este período.")

# ==================== PESTAÑA 2: REGISTRAR INGRESO/GASTO ====================
with tab2:
    st.header("Registrar Nuevo Movimiento")
    
    # Selector de tipo de registro
    tipo_registro = st.radio("¿Qué deseas registrar?", ["💵 Ingreso", "💸 Gasto"], horizontal=True)
    
    st.divider()
    
    if tipo_registro == "💸 Gasto":
        st.subheader("Registrar Gasto")

        # Selección de fecha y categoría para análisis previo
        col1, col2 = st.columns(2)
        with col1:
            fecha_gasto = st.date_input("Fecha", datetime.now())
            categoria_gasto = st.selectbox("Categoría", CATEGORIAS_GASTO)
        with col2:
            concepto_gasto = st.text_input("Concepto", placeholder="Ej: Supermercado")
            valor_gasto = st.number_input("Valor", min_value=0.0, step=0.01, format="%.2f")


        # Análisis en tiempo real antes de guardar
        anio_gasto = fecha_gasto.year
        mes_gasto = fecha_gasto.month
        bucket_gasto = clasificar_bucket(categoria_gasto)
        resumen = resumen_buckets(anio_gasto, mes_gasto)

        st.markdown(f"**Este gasto se descontará del bucket:** :orange[**{bucket_gasto}**]")

        # Calcular saldo total de la cuenta (ingresos - gastos - ahorro del periodo)
        total_ingresos = obtener_ingresos(anio_gasto, mes_gasto)["valor_total"].sum()
        total_gastos = obtener_gastos(anio_gasto, mes_gasto)["valor"].sum()
        total_ahorro = obtener_ingresos(anio_gasto, mes_gasto)["monto_ahorro"].sum()
        saldo_cuenta = total_ingresos - total_gastos - total_ahorro

        colb1, colb2, colb3, colb4 = st.columns(4)
        with colb1:
            st.metric(
                "💼 Necesidades disponible",
                f"${resumen['disponible']['Necesidades']:,.2f}",
                delta=f"- ${valor_gasto:,.2f}" if bucket_gasto == "Necesidades" and valor_gasto > 0 else None,
                help="Presupuesto menos gastado en necesidades este mes"
            )
        with colb2:
            st.metric(
                "🎯 Deseos disponible",
                f"${resumen['disponible']['Deseos']:,.2f}",
                delta=f"- ${valor_gasto:,.2f}" if bucket_gasto == "Deseos" and valor_gasto > 0 else None,
                help="Presupuesto menos gastado en deseos este mes"
            )
        with colb3:
            st.metric(
                "🏦 Ahorro acumulado",
                f"${resumen['disponible']['Ahorro']:,.2f}",
                help="Total acumulado en ahorro este mes (no se descuenta por gastos)"
            )
        with colb4:
            st.metric(
                "💰 Saldo cuenta",
                f"${saldo_cuenta:,.2f}",
                help="Ingresos - gastos - ahorro del mes"
            )

        if bucket_gasto == "Ahorro":
            st.warning("El bucket 'Ahorro' es acumulativo. Este gasto no descuenta de tu ahorro, solo se registra como gasto. Si quieres registrar un retiro de ahorro, usa una categoría especial.")

        with st.form("form_gasto", clear_on_submit=True):
            st.write(":grey[Confirma los datos y guarda el gasto]")
            submit_gasto = st.form_submit_button("💾 Guardar Gasto", use_container_width=True)

            if submit_gasto:
                if concepto_gasto and valor_gasto > 0:
                    insertar_gasto(
                        fecha_gasto.strftime("%Y-%m-%d"),
                        categoria_gasto,
                        concepto_gasto,
                        valor_gasto
                    )
                    # Recalcular resumen tras guardar
                    resumen_post = resumen_buckets(anio_gasto, mes_gasto)
                    total_ingresos_post = obtener_ingresos(anio_gasto, mes_gasto)["valor_total"].sum()
                    total_gastos_post = obtener_gastos(anio_gasto, mes_gasto)["valor"].sum()
                    saldo_cuenta_post = total_ingresos_post - total_gastos_post
                    st.success(f"✅ Gasto de ${valor_gasto:,.2f} registrado exitosamente en bucket {bucket_gasto}!")
                    st.info(
                        f"**Necesidades:** Disponible ${resumen_post['disponible']['Necesidades']:,.2f} | Gastado ${resumen_post['gastado']['Necesidades']:,.2f} de ${resumen_post['presupuesto']['Necesidades']:,.2f}\n"
                        f"**Deseos:** Disponible ${resumen_post['disponible']['Deseos']:,.2f} | Gastado ${resumen_post['gastado']['Deseos']:,.2f} de ${resumen_post['presupuesto']['Deseos']:,.2f}\n"
                        f"**Ahorro acumulado:** ${resumen_post['disponible']['Ahorro']:,.2f} (no se descuenta por gastos)\n"
                        f"**Saldo cuenta:** ${saldo_cuenta_post:,.2f}"
                    )
                    st.rerun()
                else:
                    st.error("⚠️ Por favor completa todos los campos correctamente.")
    
    else:  # Ingreso
        st.subheader("Registrar Ingreso")
        
        with st.form("form_ingreso", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                fecha_ingreso = st.date_input("Fecha", datetime.now())
                concepto_ingreso = st.text_input("Concepto", placeholder="Ej: Salario mensual")
                valor_ingreso = st.number_input("Valor Total", min_value=0.0, step=0.01, format="%.2f")
            
            with col2:
                st.markdown("**Distribución de porcentajes:**")
                porc_necesidades = st.number_input("% Necesidades básicas", 
                                                   min_value=0.0, max_value=100.0, 
                                                   value=80.0, step=1.0)
                porc_deseos = st.number_input("% Deseos", 
                                             min_value=0.0, max_value=100.0, 
                                             value=10.0, step=1.0)
                porc_ahorro = st.number_input("% Ahorro", 
                                             min_value=0.0, max_value=100.0, 
                                             value=10.0, step=1.0)
            
            # Validación de porcentajes
            suma_porcentajes = porc_necesidades + porc_deseos + porc_ahorro
            
            if suma_porcentajes != 100:
                st.warning(f"⚠️ La suma de porcentajes es {suma_porcentajes}%. Debe ser exactamente 100%.")
            
            # Previsualización de montos
            if valor_ingreso > 0:
                st.markdown("**Vista previa de distribución:**")
                col_prev1, col_prev2, col_prev3 = st.columns(3)
                
                with col_prev1:
                    st.info(f"Necesidades: ${valor_ingreso * (porc_necesidades/100):,.2f}")
                with col_prev2:
                    st.info(f"Deseos: ${valor_ingreso * (porc_deseos/100):,.2f}")
                with col_prev3:
                    st.info(f"Ahorro: ${valor_ingreso * (porc_ahorro/100):,.2f}")
            
            submit_ingreso = st.form_submit_button("💾 Guardar Ingreso", use_container_width=True)
            
            if submit_ingreso:
                if concepto_ingreso and valor_ingreso > 0 and suma_porcentajes == 100:
                    insertar_ingreso(
                        fecha_ingreso.strftime("%Y-%m-%d"),
                        concepto_ingreso,
                        valor_ingreso,
                        porc_necesidades,
                        porc_deseos,
                        porc_ahorro
                    )
                    st.success(f"✅ Ingreso de ${valor_ingreso:,.2f} registrado exitosamente!")
                    st.rerun()
                else:
                    st.error("⚠️ Por favor completa todos los campos y verifica que los porcentajes sumen 100%.")

# ==================== PESTAÑA 3: ELIMINAR REGISTROS ====================
with tab3:
    st.header("Eliminar Registros")
    
    tipo_eliminacion = st.radio("¿Qué tipo de registro deseas eliminar?", 
                                ["💵 Ingresos", "💸 Gastos"], 
                                horizontal=True)
    
    st.divider()
    
    if tipo_eliminacion == "💵 Ingresos":
        ingresos_todos = obtener_ingresos()
        
        if not ingresos_todos.empty:
            # Mostrar tabla de ingresos
            st.subheader("Ingresos Registrados")
            
            # Formatear DataFrame para mostrar
            df_display = ingresos_todos[['id_ingreso', 'fecha', 'concepto', 'valor_total']].copy()
            df_display.columns = ['ID', 'Fecha', 'Concepto', 'Valor Total']
            
            st.dataframe(
                df_display.style.format({'Valor Total': '${:,.2f}'}),
                use_container_width=True,
                hide_index=True
            )
            
            # Selector para eliminar
            col1, col2 = st.columns([2, 1])
            
            with col1:
                id_eliminar = st.selectbox(
                    "Selecciona el ID del ingreso a eliminar",
                    ingresos_todos['id_ingreso'].tolist(),
                    format_func=lambda x: f"ID {x} - {ingresos_todos[ingresos_todos['id_ingreso']==x]['concepto'].values[0]}"
                )
            
            with col2:
                st.write("")  # Espaciado
                st.write("")
                if st.button("🗑️ Eliminar Ingreso", type="primary", use_container_width=True):
                    eliminar_ingreso(id_eliminar)
                    st.success(f"✅ Ingreso #{id_eliminar} eliminado exitosamente!")
                    st.rerun()
        else:
            st.info("No hay ingresos registrados para eliminar.")
    
    else:  # Gastos
        gastos_todos = obtener_gastos()
        
        if not gastos_todos.empty:
            # Mostrar tabla de gastos
            st.subheader("Gastos Registrados")
            
            # Formatear DataFrame para mostrar
            df_display = gastos_todos[['id_gasto', 'fecha', 'categoria', 'concepto', 'valor']].copy()
            df_display.columns = ['ID', 'Fecha', 'Categoría', 'Concepto', 'Valor']
            
            st.dataframe(
                df_display.style.format({'Valor': '${:,.2f}'}),
                use_container_width=True,
                hide_index=True
            )
            
            # Selector para eliminar
            col1, col2 = st.columns([2, 1])
            
            with col1:
                id_eliminar = st.selectbox(
                    "Selecciona el ID del gasto a eliminar",
                    gastos_todos['id_gasto'].tolist(),
                    format_func=lambda x: f"ID {x} - {gastos_todos[gastos_todos['id_gasto']==x]['concepto'].values[0]}"
                )
            
            with col2:
                st.write("")  # Espaciado
                st.write("")
                if st.button("🗑️ Eliminar Gasto", type="primary", use_container_width=True):
                    eliminar_gasto(id_eliminar)
                    st.success(f"✅ Gasto #{id_eliminar} eliminado exitosamente!")
                    st.rerun()
        else:
            st.info("No hay gastos registrados para eliminar.")

# ==================== FOOTER ====================
st.divider()
st.caption("💡 Base de datos: finanzas_personales.db | Regla 80/10/10 para finanzas equilibradas")