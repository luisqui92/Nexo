'use strict';
const slides=[...document.querySelectorAll('.slide')];let current=0;
function showSlide(index){current=Math.max(0,Math.min(slides.length-1,index));slides.forEach((s,i)=>{s.classList.toggle('active',i===current);s.setAttribute('aria-hidden',i!==current)});document.getElementById('counter').textContent=(current+1)+' / '+slides.length;document.getElementById('prev').disabled=current===0;document.getElementById('next').disabled=current===slides.length-1;window.scrollTo(0,0)}
document.getElementById('prev').onclick=()=>showSlide(current-1);document.getElementById('next').onclick=()=>showSlide(current+1);document.getElementById('print').onclick=()=>window.print();
document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown'].includes(e.key)){e.preventDefault();showSlide(current+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();showSlide(current-1)}});showSlide(0);
