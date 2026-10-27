"""Modelo exploratorio de agua en dos capas; no certificado para tránsito de maquinaria."""
from dataclasses import dataclass
import math
import pandas as pd

SUELOS = {
    # Parámetros ilustrativos, NO valores de diseño ni mediciones locales
    'Arenoso': dict(ks=40.0, psi=50.0, sat=.43, fc=.15, wp=.06),
    'Franco arenoso': dict(ks=18.0, psi=90.0, sat=.43, fc=.23, wp=.10),
    'Franco': dict(ks=8.0, psi=110.0, sat=.46, fc=.30, wp=.13),
    'Franco arcilloso': dict(ks=3.0, psi=180.0, sat=.48, fc=.36, wp=.20),
    'Arcilloso': dict(ks=1.0, psi=250.0, sat=.50, fc=.40, wp=.25),
}

@dataclass
class Config:
    ks: float = 8.0                    # mm/h
    psi: float = 110.0                 # mm
    theta_sat: float = .46
    theta_fc: float = .30
    theta_wp: float = .13
    theta0: float = .32
    capa_sup_mm: float = 150.0
    capa_inf_mm: float = 350.0
    cobertura: float = .35            # fracción 0-1
    drenaje_factor: float = .025       # fracción del exceso sobre CC por hora
    encharcamiento_max_mm: float = 5.0 # almacenamiento superficial al final de hora
    inicio_ventana_pct: float = 85.0   # fracción de humedad relativa CC->saturación
    fin_ventana_pct: float = 65.0      # más exigente para 'favorable'
    resistencia_mpa: float | None = None
    resistencia_min_mpa: float = 1.0  # supuesto a calibrar por equipo, suelo y operación


def validar(c: Config):
    if not (0 < c.theta_wp < c.theta_fc < c.theta_sat < 0.8):
        raise ValueError('Debe cumplirse 0 < punto de marchitez < capacidad de campo < saturación < 0.8.')
    if not (c.theta_wp <= c.theta0 <= c.theta_sat):
        raise ValueError('La humedad inicial debe estar entre punto de marchitez y saturación.')
    if min(c.ks,c.psi,c.capa_sup_mm,c.capa_inf_mm) <= 0:
        raise ValueError('Conductividad, succión y espesores deben ser positivos.')
    if not (0 <= c.cobertura <= 1 and 0 <= c.drenaje_factor <= 1):
        raise ValueError('Cobertura y factor de drenaje deben estar entre 0 y 1.')
    if not 0 <= c.fin_ventana_pct <= c.inicio_ventana_pct <= 100:
        raise ValueError('Los umbrales de humedad deben cumplir 0 ≤ favorable ≤ precaución ≤ 100.')


def simular(datos: pd.DataFrame, c: Config):
    """Datos horarios: fecha, precipitacion_mm, eto_mm [opcional], riego_mm [opcional].

    Conservación: P + riego = escorrentía + evaporación + transpiración + drenaje
    + variación de almacenamiento (capas + lámina superficial).
    Green-Ampt explícito horario, con subpasos y reinicio aproximado en secado prolongado.
    """
    validar(c)
    if datos.empty:
        raise ValueError('Se requiere al menos una hora de datos.')
    datos = datos.copy().reset_index(drop=True)
    for col in ['precipitacion_mm','eto_mm','riego_mm']:
        if col not in datos:
            datos[col] = 0.0
        datos[col] = pd.to_numeric(datos[col],errors='coerce').fillna(0.0)
        if (datos[col] < 0).any():
            raise ValueError(f'{col}: no se permiten valores negativos.')
    upper = c.theta0 * c.capa_sup_mm
    lower = c.theta0 * c.capa_inf_mm
    cap_u,cap_l = c.theta_sat*c.capa_sup_mm,c.theta_sat*c.capa_inf_mm
    fc_u,fc_l = c.theta_fc*c.capa_sup_mm,c.theta_fc*c.capa_inf_mm
    wp_u,wp_l = c.theta_wp*c.capa_sup_mm,c.theta_wp*c.capa_inf_mm
    surface = 0.0
    f_event = 0.0
    dry_hours = 0
    rows=[]
    initial_storage=upper+lower+surface
    for _, r in datos.iterrows():
        p=float(r.precipitacion_mm)
        irrigation=float(r.riego_mm)
        eto=float(r.eto_mm)
        # Subpasos para aproximar variación de capacidad de infiltración durante tormentas
        infiltracion=0.0
        runoff=0.0
        infiltracion_potencial=0.0
        for _step in range(12):
            applied=(p+irrigation)/12.0
            surface+=applied
            deficit=max(c.theta_sat-upper/c.capa_sup_mm,0)
            # Se reinicia frente al pasar a un evento nuevo tras secado prolongado.
            fcap=c.ks*(1.0+c.psi*deficit/max(f_event,1.0))
            potential=fcap/12.0
            infiltracion_potencial+=potential
            # Infiltración limitada por disponibilidad, capacidad y almacenamiento TOTAL del perfil
            available_storage=max(0,(cap_u-upper)+(cap_l-lower))
            take=min(surface,potential,available_storage)
            surface-=take
            infiltracion+=take
            f_event+=take
            upper+=take
            # Exceso de saturación capa superior transfiere a inferior inmediatamente
            transfer=min(max(upper-cap_u,0),max(cap_l-lower,0))
            upper-=transfer
            lower+=transfer
            if surface>c.encharcamiento_max_mm:
                runoff+=surface-c.encharcamiento_max_mm
                surface=c.encharcamiento_max_mm
        # Evaporación limitada a agua disponible sobre punto de marchitez
        evaporacion=min(eto*(1-c.cobertura),max(upper-wp_u,0)+surface)
        de_surface=min(surface,evaporacion)
        surface-=de_surface
        upper-=evaporacion-de_surface
        # Transpiración desde ambas capas, fracción según cobertura (estimación exploratoria)
        trans_pot=eto*c.cobertura
        from_upper=min(trans_pot*.6,max(upper-wp_u,0))
        upper-=from_upper
        from_lower=min(trans_pot-from_upper,max(lower-wp_l,0))
        lower-=from_lower
        trans=from_upper+from_lower
        # Drenaje entre capas y percolación profunda sobre capacidad de campo
        to_lower=min(max(upper-fc_u,0)*c.drenaje_factor,max(cap_l-lower,0))
        upper-=to_lower
        lower+=to_lower
        deep=min(max(lower-fc_l,0)*c.drenaje_factor,max(lower-wp_l,0))
        lower-=deep
        # Si no llueve y el agua superficial terminó, evento concluye gradualmente
        if p+irrigation<1e-12 and surface<1e-9:
            dry_hours+=1
            if dry_hours>=24:
                f_event=0.0
        else:
            dry_hours=0
        theta_u=upper/c.capa_sup_mm
        theta_l=lower/c.capa_inf_mm
        # Porcentaje entre CC y saturación: <0 significa más seco que capacidad de campo
        wetness=100*(theta_u-c.theta_fc)/(c.theta_sat-c.theta_fc)
        if surface>0.1 or wetness>c.inicio_ventana_pct:
            estado='No ingresar (preliminar)'
        elif wetness>c.fin_ventana_pct:
            estado='Precaución (preliminar)'
        else:
            estado='Humedad favorable (no habilita ingreso)'
        if c.resistencia_mpa is not None and c.resistencia_mpa < c.resistencia_min_mpa:
            estado='No ingresar (resistencia baja)'
        rows.append(dict(fecha=r['fecha'],precipitacion_mm=p,riego_mm=irrigation,eto_mm=eto,
             infiltracion_mm=infiltracion,escorrentia_mm=runoff,evaporacion_mm=evaporacion,
             transpiracion_mm=trans,drenaje_profundo_mm=deep,transferencia_mm=to_lower,
             agua_superficial_mm=surface,humedad_superficial=theta_u,humedad_profunda=theta_l,
             humedad_relativa_cc_saturacion_pct=wetness,estado=estado,
             almacenamiento_mm=upper+lower+surface))
    out=pd.DataFrame(rows)
    entradas=out.precipitacion_mm.sum()+out.riego_mm.sum()
    salidas=sum(out[k].sum() for k in ['escorrentia_mm','evaporacion_mm','transpiracion_mm','drenaje_profundo_mm'])
    residual=entradas-salidas-(out.almacenamiento_mm.iloc[-1]-initial_storage)
    return out, residual


def evaluar_transito(resultado, cfg, masa_kg, numero_ruedas, fraccion_eje,
                    presion_contacto_kpa, resistencia_mpa=None,
                    indice_seguridad=2.0, horas_persistencia=6):
    """Cribado exploratorio, NO cálculo validado de capacidad portante.

    La resistencia al penetrómetro (índice de cono) no equivale a una presión
    admisible. El índice resistencia/presión de contacto es solo un INDICADOR
    empírico cuya cota debe calibrarse con datos de campo locales.
    """
    if masa_kg <= 0 or numero_ruedas < 2 or not (0 < fraccion_eje <= 1) or presion_contacto_kpa <= 0:
        raise ValueError('Verifica la masa, cantidad de ruedas, fracción de carga y presión de contacto.')
    if horas_persistencia < 1:
        raise ValueError('Las horas consecutivas deben ser mayores que cero.')
    # Carga por rueda del eje crítico (fracción de masa soportada por el eje, en dos ruedas).
    carga_rueda_kn = masa_kg * 9.81 * fraccion_eje / 2 / 1000
    area_contacto_m2 = carga_rueda_kn / presion_contacto_kpa
    equivalente_diametro_m = (4 * area_contacto_m2 / math.pi) ** .5
    df = resultado.copy()
    df['humedad_favorable'] = (df['estado'] == 'Humedad favorable (no habilita ingreso)')
    df['condicion_humedad'] = df['estado'].map(lambda x: 'Favorable' if x == 'Humedad favorable (no habilita ingreso)' else ('Precaución' if x == 'Precaución (preliminar)' else 'No favorable'))
    # Resistencia constante tomada en un instante no sirve para predecir la evolución de resistencia futura.
    if resistencia_mpa is not None:
        razon = resistencia_mpa * 1000 / presion_contacto_kpa
        respaldo = razon >= indice_seguridad
        df['cribado_resistencia'] = 'Cumple umbral exploratorio' if respaldo else 'No cumple umbral exploratorio'
    else:
        razon = None
        df['cribado_resistencia'] = 'Sin medición de resistencia'
    con_agua = (df['precipitacion_mm'] + df['riego_mm']) > 1e-9
    indices = df.index[con_agua]
    ultima_lluvia = int(indices[-1]) if len(indices) else -1
    i_primer = None
    i_confirmado = None
    for i in range(ultima_lluvia+1, len(df)-horas_persistencia+1):
        if bool(df['humedad_favorable'].iloc[i:i+horas_persistencia].all()):
            i_primer = i
            i_confirmado = i+horas_persistencia-1
            break
    resultado_ventana = None
    if i_primer is not None:
        tll = pd.to_datetime(df.iloc[ultima_lluvia]['fecha']) if ultima_lluvia >= 0 else None
        inicio = pd.to_datetime(df.iloc[i_primer]['fecha'])
        confirmacion = pd.to_datetime(df.iloc[i_confirmado]['fecha'])
        resultado_ventana = {'inicio': inicio, 'confirmacion': confirmacion,
                             'horas_desde_ultima_lluvia_a_confirmacion': ((confirmacion-tll).total_seconds()/3600 if tll is not None else None)}
    return df, {
        'carga_por_rueda_kn': carga_rueda_kn,
        'area_contacto_m2': area_contacto_m2,
        'diametro_equivalente_m': equivalente_diametro_m,
        'indice_resistencia_presion': razon,
        'umbral_indice': indice_seguridad,
        'ventana': resultado_ventana,
        'resistencia_medida': resistencia_mpa is not None,
    }
