"""Training rules; no guessed outcomes enter confirmed shooting statistics."""
import math


def validate_shots(shots, duration):
    if not isinstance(shots, list) or len(shots) > 2000:
        raise ValueError('投篮记录格式错误或数量过多')
    ids = set()
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError('投篮记录格式错误')
        ident = shot.get('id')
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError('每次出手需要唯一编号')
        ids.add(ident)
        times = [shot.get(k) for k in ('start', 'release', 'end')]
        if not all(type(t) in (int, float) and math.isfinite(t) for t in times):
            raise ValueError('时间必须为有效数字')
        if not 0 <= times[0] <= times[1] < times[2] <= duration + .05:
            raise ValueError('出手时间超出视频范围')
        if shot.get('outcome') not in ('made', 'missed', 'unknown'):
            raise ValueError('投篮结果无效')
        if type(shot.get('reviewed')) is not bool:
            raise ValueError('核对状态无效')
        if len(str(shot.get('note', ''))) > 2000:
            raise ValueError('备注过长')
    return sorted(shots, key=lambda s: s['release'])


def statistics(shots):
    known = [s for s in shots if s['reviewed'] and s['outcome'] in ('made', 'missed')]
    made = sum(s['outcome'] == 'made' for s in known)
    return dict(attempts=len(known), made=made, pending=len(shots)-len(known),
                percentage=round(made / len(known) * 100, 1) if known else None)


def report(session):
    if session.get('reviewReport') and session.get('reviewReportRevision') == session.get('revision'):
        return session['reviewReport']
    stats = statistics(session['shots'])
    percentage = f"{stats['percentage']:.1f}%" if stats['percentage'] is not None else '暂无数据'
    observed = [s.get('note', '').strip() for s in session['shots'] if s['reviewed'] and s.get('note', '').strip()]
    text = f"球员训练记录与复盘\n{session['title']} · {session['date']}\n\n已核对出手 {stats['attempts']} 次，命中 {stats['made']} 次，命中率 {percentage}。结果待定 {stats['pending']} 次。\n统计仅代表这段录像中已确认结果的出手，不代表整场训练。"
    text += '\n\n复盘\n'
    if observed:
        text += '\n'.join('• '+n for n in list(dict.fromkeys(observed))[:6])
    else:
        text += '暂未记录可验证的动作问题。核对时可补充站位、脚步或出手节奏的具体观察；仅凭命中率不能判断动作缺陷。'
    text += '\n\n改进建议（基于记录的通用练习建议）\n保持拍摄机位与练习条件一致，并区分定点、运球后投篮和罚球，以便下次做有效比较。'
    if stats['pending']:
        text += '\n先核对待定片段，再判断本次命中率。'
    text += '\n\n下次训练计划 · 约 60 分钟 / 120 次投篮\n0–8 分钟：热身和脚步准备。\n8–15 分钟：近筐动作练习 20 次，固定收球与出手节奏。\n15–30 分钟：五个定点，每点 8 次，共 40 次。\n30–42 分钟：左右各 10 次运球后投篮，共 20 次。\n42–50 分钟：重复同一站位投篮 20 次，记录每球结果。\n50–57 分钟：罚球 20 次，保持固定准备流程。\n57–60 分钟：整理与记录。\n训练量可按体感调整；下次复盘优先比较相同练习条件的数据。'
    return text
