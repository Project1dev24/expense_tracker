from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

def generate_settlement_pdf(trip, settlements, balances, user_map):
    """Generate a PDF report for trip settlements using ReportLab"""
    try:
        # Create a buffer to store PDF
        buffer = BytesIO()
        
        # Create the PDF document using reportlab
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Container for the 'Flowable' objects
        elements = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Add title
        elements.append(Paragraph(f"Trip Settlement Report: {trip.name}", title_style))
        elements.append(Spacer(1, 20))
        
        # Add trip details
        elements.append(Paragraph("Trip Details", heading_style))
        elements.append(Spacer(1, 10))
        
        # Calculate total expenses from balances
        total_expenses = sum(abs(amount) for amount in balances.values() if amount < 0)
        
        trip_details = [
            ["Trip Name:", trip.name],
            ["Date:", datetime.now().strftime('%d %b %Y')],
            ["Total Expenses:", f"₹{total_expenses:.2f}"]
        ]
        trip_table = Table(trip_details, colWidths=[100, 300])
        trip_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(trip_table)
        elements.append(Spacer(1, 20))

        # Add balances section
        if balances:
            elements.append(Paragraph("Current Balances", heading_style))
            elements.append(Spacer(1, 10))
            
            # Create balances table
            balance_data = [["Participant", "Balance"]]
            for user_id, amount in balances.items():
                balance_data.append([
                    user_map.get(str(user_id), "Unknown"),
                    f"₹{amount:.2f}"
                ])
            
            balance_table = Table(balance_data, colWidths=[300, 100])
            balance_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(balance_table)
            elements.append(Spacer(1, 20))

        # Add settlements section
        if settlements:
            elements.append(Paragraph("Settlements", heading_style))
            elements.append(Spacer(1, 10))
            
            # Create settlements table
            settlement_data = [["From", "To", "Amount"]]
            for settlement in settlements:
                settlement_data.append([
                    user_map.get(str(settlement['from_user']), "Unknown"),
                    user_map.get(str(settlement['to_user']), "Unknown"),
                    f"₹{settlement['amount']:.2f}"
                ])
            
            settlement_table = Table(settlement_data, colWidths=[160, 160, 80])
            settlement_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(settlement_table)

        # Build PDF
        doc.build(elements)
        
        # Get the value of the BytesIO buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise
