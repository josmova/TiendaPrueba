from django.db.models.signals import post_save
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.shortcuts import reverse
from django_countries.fields import CountryField


CATEGORY_CHOICES = (
    ('S', 'Computadoras'),
    ('SW', 'Impresoras'),
    ('OW', 'Ratones')
)

LABEL_CHOICES = (
    ('P', 'Primaria'),
    ('S', 'Secundary'),
    ('D', 'Peligro')
)

ADDRESS_CHOICES = (
    ('B', 'Facturación'),
    ('S', 'Envio'),
)


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)
    one_click_purchasing = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class Item(models.Model):
    title = models.CharField(max_length=100, verbose_name="Título")
    price = models.FloatField(verbose_name="Precio")
    discount_price = models.FloatField(blank=True, null=True, verbose_name="Descuento de precio")
    category = models.CharField(choices=CATEGORY_CHOICES, max_length=2, verbose_name="Categor{ia")
    label = models.CharField(choices=LABEL_CHOICES, max_length=1,verbose_name="Etiqueta")
    slug = models.SlugField()
    description = models.TextField()
    image = models.ImageField()

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:product", kwargs={
            'slug': self.slug
        })

    def get_add_to_cart_url(self):
        return reverse("core:add-to-cart", kwargs={
            'slug': self.slug
        })

    def get_remove_from_cart_url(self):
        return reverse("core:remove-from-cart", kwargs={
            'slug': self.slug
        })


class OrderItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,verbose_name="Usuario")
    ordered = models.BooleanField(default=False,verbose_name="Ordenado")
    item = models.ForeignKey(Item, on_delete=models.CASCADE,verbose_name="Articulo")
    quantity = models.IntegerField(default=1,verbose_name="Cantidad")

    def __str__(self):
        return f"{self.quantity} de {self.item.title}"

    def get_total_item_price(self):
        return self.quantity * self.item.price

    def get_total_discount_item_price(self):
        return self.quantity * self.item.discount_price

    def get_amount_saved(self):
        return self.get_total_item_price() - self.get_total_discount_item_price()

    def get_final_price(self):
        if self.item.discount_price:
            return self.get_total_discount_item_price()
        return self.get_total_item_price()


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, verbose_name="Usuario")
    ref_code = models.CharField(max_length=20, blank=True, null=True,verbose_name="Referencia Codigo")
    items = models.ManyToManyField(OrderItem,verbose_name="Articulos")
    start_date = models.DateTimeField(auto_now_add=True,verbose_name="Fecha inicio")
    ordered_date = models.DateTimeField(verbose_name="Fecha de pedido")
    ordered = models.BooleanField(default=False, verbose_name="Ordenado")
    shipping_address = models.ForeignKey(
        'Address', related_name='shipping_address', on_delete=models.SET_NULL, blank=True, null=True,verbose_name="Dirección de envio")
    billing_address = models.ForeignKey(
        'Address', related_name='billing_address', on_delete=models.SET_NULL, blank=True, null=True,verbose_name="Dirección de envio")
    payment = models.ForeignKey(
        'Payment', on_delete=models.SET_NULL, blank=True, null=True,verbose_name="Pago")
    coupon = models.ForeignKey(
        'Coupon', on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Cupon")
    being_delivered = models.BooleanField(default=False, verbose_name="Siendo entregado")
    received = models.BooleanField(default=False,verbose_name="Recibido")
    refund_requested = models.BooleanField(default=False,verbose_name="Reembolso requerido")
    refund_granted = models.BooleanField(default=False,verbose_name="Reembolso concedido")

    '''
    1. Item added to cart
    2. Adding a billing address
    (Failed checkout)
    3. Payment
    (Preprocessing, processing, packaging etc.)
    4. Being delivered
    5. Received
    6. Refunds
    '''

    def __str__(self):
        return self.user.username

    def get_total(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_final_price()
        if self.coupon:
            total -= self.coupon.amount
        return total


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, verbose_name="Usuario")
    street_address = models.CharField(max_length=100,verbose_name="Dirección")
    apartment_address = models.CharField(max_length=100,verbose_name="Dirección de la casa")
    country = CountryField(multiple=False,verbose_name="País")
    zip = models.CharField(max_length=100,verbose_name="Codigo postal")
    address_type = models.CharField(max_length=1, choices=ADDRESS_CHOICES,verbose_name="Tipo de dirección")
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name_plural = 'Direccion'
        # verbose_name_plural = 'Addresses'


class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50,verbose_name="id stripe")
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Usuario")
    amount = models.FloatField(verbose_name="Cantidad")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Tiempo")

    def __str__(self):
        return self.user.username


class Coupon(models.Model):
    code = models.CharField(max_length=15, verbose_name="Codigo")
    amount = models.FloatField(verbose_name="Cantidad")

    def __str__(self):
        return self.code


class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,verbose_name="Orden")
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    email = models.EmailField()

    def __str__(self):
        return f"{self.pk}"


def userprofile_receiver(sender, instance, created, *args, **kwargs):
    if created:
        userprofile = UserProfile.objects.create(user=instance)


post_save.connect(userprofile_receiver, sender=settings.AUTH_USER_MODEL)
