function renderVisual(target, data) {
    const steps = new Array(5).fill(0);
    for (const row of data.rows) steps[Math.min(4,Math.floor(row.estimate*5))]++;
    const staircase = node('div',undefined,'stairs');
    steps.forEach((count,index) => {
        const piece = node('figure',undefined,'step');
        const height = node('strong',count);
        height.style.minHeight = `${35+index*24}px`;
        piece.append(height,node('figcaption',`${index*20}–${(index+1)*20}%`));
        staircase.append(piece);
    });
    target.append(staircase);
}
